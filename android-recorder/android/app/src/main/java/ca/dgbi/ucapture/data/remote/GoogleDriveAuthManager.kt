package ca.dgbi.ucapture.data.remote

import android.app.Activity
import android.content.Context
import android.util.Log
import androidx.credentials.ClearCredentialStateRequest
import androidx.credentials.CredentialManager
import androidx.credentials.CustomCredential
import androidx.credentials.GetCredentialRequest
import androidx.credentials.GetCredentialResponse
import androidx.credentials.exceptions.GetCredentialException
import com.google.android.gms.auth.api.identity.AuthorizationRequest
import com.google.android.gms.auth.api.identity.AuthorizationResult
import com.google.android.gms.auth.api.identity.Identity
import com.google.android.gms.common.api.Scope
import com.google.android.libraries.identity.googleid.GetGoogleIdOption
import com.google.android.libraries.identity.googleid.GoogleIdTokenCredential
import com.google.api.client.http.javanet.NetHttpTransport
import com.google.api.client.json.gson.GsonFactory
import com.google.api.services.drive.Drive
import com.google.api.services.drive.DriveScopes
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.tasks.await
import kotlinx.coroutines.withContext
import ca.dgbi.ucapture.BuildConfig
import java.util.concurrent.atomic.AtomicLong
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Manages Google Drive authentication using Credential Manager.
 *
 * Handles sign-in, token refresh, and Drive API client creation.
 * Uses the modern Credential Manager API instead of deprecated Google Sign-In.
 */
@Singleton
class GoogleDriveAuthManager @Inject constructor(
    @ApplicationContext private val context: Context,
    private val secureTokenStorage: SecureTokenStorage
) {
    companion object {
        private const val REQUEST_AUTHORIZE = 1001
        private val WEB_CLIENT_ID = BuildConfig.GOOGLE_WEB_CLIENT_ID
        private val SCOPES = listOf(DriveScopes.DRIVE_FILE)
        // Refresh if token is older than 45 minutes (tokens expire at 60)
        private const val TOKEN_REFRESH_INTERVAL_MS = 45L * 60 * 1000
    }

    private val credentialManager = CredentialManager.create(context)
    private val authorizationClient = Identity.getAuthorizationClient(context)
    private var currentAccountEmail: String? = null
    private var accessToken: String? = null
    private var driveService: Drive? = null
    private val mutex = Mutex()

    // Track when the token was last refreshed to avoid refreshing too often
    private val lastTokenRefreshMs = AtomicLong(0L)

    /**
     * Check if user is currently signed in.
     */
    suspend fun isSignedIn(): Boolean = mutex.withLock {
        // If in-memory state exists, return true
        if (currentAccountEmail != null && accessToken != null && driveService != null) {
            return@withLock true
        }

        // Otherwise, try to restore from storage
        val storedToken = secureTokenStorage.getToken()
        val storedEmail = secureTokenStorage.getEmail()

        if (storedToken != null && storedEmail != null) {
            accessToken = storedToken
            currentAccountEmail = storedEmail
            initializeDriveService(storedToken)
            return@withLock true
        }

        false
    }

    /**
     * Sign in with Google and request Drive scope.
     *
     * Must be called from an Activity context for UI.
     *
     * @param activityContext Activity context for sign-in UI
     * @return true if sign-in successful
     */
    suspend fun signIn(activityContext: Context): Boolean = withContext(Dispatchers.Main) {
        try {
            // Step 1: Sign in with Google ID
            val googleIdOption = GetGoogleIdOption.Builder()
                .setFilterByAuthorizedAccounts(false)
                .setServerClientId(WEB_CLIENT_ID)
                .setAutoSelectEnabled(true)
                .build()

            val request = GetCredentialRequest.Builder()
                .addCredentialOption(googleIdOption)
                .build()

            val result = credentialManager.getCredential(
                context = activityContext,
                request = request
            )

            val idSignInSuccessful = handleSignInResult(result)
            if (!idSignInSuccessful) {
                return@withContext false
            }

            // Step 2: Request Drive authorization
            requestDriveAuthorization(activityContext)
        } catch (e: GetCredentialException) {
            Log.e("GoogleDriveAuthManager", "Sign-in failed", e)
            false
        } catch (e: Exception) {
            Log.e("GoogleDriveAuthManager", "Sign-in failed", e)
            false
        }
    }

    private suspend fun handleSignInResult(response: GetCredentialResponse): Boolean {
        val credential = response.credential

        return when (credential) {
            is CustomCredential -> {
                if (credential.type == GoogleIdTokenCredential.TYPE_GOOGLE_ID_TOKEN_CREDENTIAL) {
                    try {
                        val googleIdTokenCredential = GoogleIdTokenCredential.createFrom(credential.data)
                        mutex.withLock {
                            currentAccountEmail = googleIdTokenCredential.id
                        }
                        true
                    } catch (e: Exception) {
                        Log.e("GoogleDriveAuthManager", "Failed to parse credential", e)
                        false
                    }
                } else {
                    Log.w("GoogleDriveAuthManager", "Unexpected credential type: ${credential.type}")
                    false
                }
            }
            else -> {
                Log.w("GoogleDriveAuthManager", "Unexpected credential class: ${credential::class.simpleName}")
                false
            }
        }
    }

    /**
     * Request Drive API authorization using AuthorizationRequest.
     *
     * This obtains the OAuth access token needed for Drive API calls.
     */
    private suspend fun requestDriveAuthorization(activityContext: Context): Boolean = withContext(Dispatchers.Main) {
        try {
            val authorizationRequest = AuthorizationRequest.builder()
                .setRequestedScopes(listOf(Scope(DriveScopes.DRIVE_FILE)))
                .build()

            val authorizationResult = authorizationClient
                .authorize(authorizationRequest)
                .await()

            handleAuthorizationResult(authorizationResult, activityContext)
        } catch (e: Exception) {
            Log.e("GoogleDriveAuthManager", "Authorization failed", e)
            false
        }
    }

    private suspend fun handleAuthorizationResult(result: AuthorizationResult, activityContext: Context): Boolean {
        if (result.hasResolution()) {
            try {
                val pendingIntent = result.pendingIntent
                if (pendingIntent != null && activityContext is Activity) {
                    activityContext.startIntentSenderForResult(
                        pendingIntent.intentSender,
                        REQUEST_AUTHORIZE,
                        null, 0, 0, 0
                    )
                    return false
                }
            } catch (e: Exception) {
                Log.e("GoogleDriveAuthManager", "Failed to launch consent", e)
            }
            return false
        }

        val token = result.accessToken
        if (token == null) {
            Log.e("GoogleDriveAuthManager", "No access token in authorization result")
            return false
        }

        mutex.withLock {
            accessToken = token
        }

        secureTokenStorage.saveToken(token)
        val email = mutex.withLock { currentAccountEmail }
        if (email != null) {
            secureTokenStorage.saveEmail(email)
        }

        initializeDriveService()
        lastTokenRefreshMs.set(System.currentTimeMillis())
        return true
    }

    private suspend fun initializeDriveService(token: String? = null) = withContext(Dispatchers.IO) {
        val tokenToUse = token ?: accessToken ?: return@withContext

        val credential = object : com.google.api.client.http.HttpRequestInitializer {
            override fun initialize(request: com.google.api.client.http.HttpRequest) {
                request.headers.authorization = "Bearer $tokenToUse"
            }
        }

        driveService = Drive.Builder(
            NetHttpTransport(),
            GsonFactory.getDefaultInstance(),
            credential
        )
            .setApplicationName("uCapture")
            .build()
    }

    /**
     * Silently refresh the access token via AuthorizationClient.
     *
     * This doesn't require UI since the user already granted Drive scope.
     * Returns true if a fresh token was obtained.
     */
    suspend fun refreshToken(): Boolean = withContext(Dispatchers.IO) {
        try {
            val authorizationRequest = AuthorizationRequest.builder()
                .setRequestedScopes(listOf(Scope(DriveScopes.DRIVE_FILE)))
                .build()

            val authorizationResult = authorizationClient
                .authorize(authorizationRequest)
                .await()

            if (authorizationResult.hasResolution()) {
                Log.w("GoogleDriveAuthManager", "Token refresh needs user interaction")
                return@withContext false
            }

            val token = authorizationResult.accessToken
            if (token == null) {
                Log.e("GoogleDriveAuthManager", "Token refresh returned no token")
                return@withContext false
            }

            mutex.withLock {
                accessToken = token
            }
            secureTokenStorage.saveToken(token)
            initializeDriveService(token)
            lastTokenRefreshMs.set(System.currentTimeMillis())
            true
        } catch (e: Exception) {
            Log.e("GoogleDriveAuthManager", "Token refresh failed", e)
            false
        }
    }

    /**
     * Ensure we have a fresh token before making API calls.
     *
     * Proactively refreshes if the token is older than 45 minutes.
     * Returns true if we have a valid (or freshly refreshed) token.
     */
    suspend fun ensureFreshToken(): Boolean {
        if (!isSignedIn()) return false

        val elapsed = System.currentTimeMillis() - lastTokenRefreshMs.get()
        if (lastTokenRefreshMs.get() == 0L || elapsed > TOKEN_REFRESH_INTERVAL_MS) {
            return refreshToken()
        }
        return true
    }

    /**
     * Get the Drive service instance.
     *
     * @throws IllegalStateException if not signed in
     */
    suspend fun getDriveService(): Drive = mutex.withLock {
        driveService ?: throw IllegalStateException("Not signed in to Google Drive")
    }

    /**
     * Sign out and clear credentials.
     */
    suspend fun signOut() = withContext(Dispatchers.IO) {
        credentialManager.clearCredentialState(ClearCredentialStateRequest())
        secureTokenStorage.clear()
        mutex.withLock {
            currentAccountEmail = null
            accessToken = null
            driveService = null
        }
    }

    /**
     * Get the current signed-in account email.
     */
    suspend fun getCurrentAccountEmail(): String? = mutex.withLock {
        currentAccountEmail
    }
}
