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
    @ApplicationContext private val context: Context
) {
    companion object {
        private const val REQUEST_AUTHORIZE = 1001
        private val WEB_CLIENT_ID = BuildConfig.GOOGLE_WEB_CLIENT_ID
        private val SCOPES = listOf(DriveScopes.DRIVE_FILE)
    }

    private val credentialManager = CredentialManager.create(context)
    private val authorizationClient = Identity.getAuthorizationClient(context)
    private var currentAccountEmail: String? = null
    private var accessToken: String? = null
    private var driveService: Drive? = null
    private val mutex = Mutex()

    /**
     * Check if user is currently signed in.
     */
    suspend fun isSignedIn(): Boolean = mutex.withLock {
        currentAccountEmail != null && accessToken != null && driveService != null
    }

    /**
     * Sign in with Google and request Drive scope.
     *
     * Must be called from an Activity context for UI.
     *
     * @param activityContext Activity context for sign-in UI
     * @return true if sign-in successful
     */
    suspend fun signIn(activityContext: Context): Boolean = withContext(Dispatchers.IO) {
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
            false
        } catch (e: Exception) {
            false
        }
    }

    private suspend fun handleSignInResult(response: GetCredentialResponse): Boolean {
        val credential = response.credential

        return when (credential) {
            is CustomCredential -> {
                if (credential.type == GoogleIdTokenCredential.TYPE_GOOGLE_ID_TOKEN_CREDENTIAL) {
                    val googleIdTokenCredential = GoogleIdTokenCredential.createFrom(credential.data)
                    mutex.withLock {
                        currentAccountEmail = googleIdTokenCredential.id
                    }
                    true
                } else {
                    false
                }
            }
            else -> false
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
            // User needs to grant permission - launch the consent UI
            Log.d("GoogleDriveAuthManager", "Authorization needs resolution, launching consent")
            try {
                val pendingIntent = result.pendingIntent
                if (pendingIntent != null && activityContext is Activity) {
                    activityContext.startIntentSenderForResult(
                        pendingIntent.intentSender,
                        REQUEST_AUTHORIZE,
                        null, 0, 0, 0
                    )
                    // Note: Result will come back to onActivityResult
                    // For now, return false - user needs to sign in again after granting
                    return false
                }
            } catch (e: Exception) {
                Log.e("GoogleDriveAuthManager", "Failed to launch consent", e)
            }
            return false
        }

        val token = result.accessToken
        if (token == null) {
            Log.e("GoogleDriveAuthManager", "No access token in result")
            return false
        }

        Log.d("GoogleDriveAuthManager", "Got access token, initializing Drive service")
        mutex.withLock {
            accessToken = token
        }

        initializeDriveService()
        return true
    }

    private suspend fun initializeDriveService() = withContext(Dispatchers.IO) {
        val token = mutex.withLock { accessToken } ?: return@withContext

        // Create a credential that uses the access token
        val credential = object : com.google.api.client.http.HttpRequestInitializer {
            override fun initialize(request: com.google.api.client.http.HttpRequest) {
                request.headers.authorization = "Bearer $token"
            }
        }

        val service = Drive.Builder(
            NetHttpTransport(),
            GsonFactory.getDefaultInstance(),
            credential
        )
            .setApplicationName("uCapture")
            .build()

        mutex.withLock {
            driveService = service
        }
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
