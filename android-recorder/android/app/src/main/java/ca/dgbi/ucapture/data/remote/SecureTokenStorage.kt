package ca.dgbi.ucapture.data.remote

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class SecureTokenStorage @Inject constructor(
    @ApplicationContext private val context: Context
) {
    companion object {
        private const val PREFS_NAME = "ucapture_secure_prefs"
        private const val KEY_ACCESS_TOKEN = "access_token"
        private const val KEY_ACCOUNT_EMAIL = "account_email"
    }

    private val masterKey: MasterKey by lazy {
        MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
    }

    private val encryptedPrefs: SharedPreferences by lazy {
        EncryptedSharedPreferences.create(
            context,
            PREFS_NAME,
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
    }

    fun saveToken(token: String) {
        encryptedPrefs.edit().putString(KEY_ACCESS_TOKEN, token).apply()
    }

    fun getToken(): String? {
        return encryptedPrefs.getString(KEY_ACCESS_TOKEN, null)
    }

    fun saveEmail(email: String) {
        encryptedPrefs.edit().putString(KEY_ACCOUNT_EMAIL, email).apply()
    }

    fun getEmail(): String? {
        return encryptedPrefs.getString(KEY_ACCOUNT_EMAIL, null)
    }

    fun clear() {
        encryptedPrefs.edit().clear().apply()
    }
}
