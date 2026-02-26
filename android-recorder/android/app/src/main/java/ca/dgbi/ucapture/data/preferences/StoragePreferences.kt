package ca.dgbi.ucapture.data.preferences

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

private val Context.storagePreferences by preferencesDataStore("storage_preferences")

/**
 * Manages storage backend preference (Cloudflare Worker vs Google Drive).
 *
 * Allows switching between upload targets without rebuilding the app.
 */
@Singleton
class StoragePreferences @Inject constructor(
    @ApplicationContext private val context: Context
) {
    companion object {
        private val USE_CLOUDFLARE_WORKER = booleanPreferencesKey("use_cloudflare_worker")
        private const val DEFAULT_USE_CLOUDFLARE = true
    }

    /**
     * Flow that emits the current storage backend preference.
     * true = Cloudflare Worker, false = Google Drive
     */
    val useCloudflareWorker: Flow<Boolean> = context.storagePreferences.data.map { preferences ->
        preferences[USE_CLOUDFLARE_WORKER] ?: DEFAULT_USE_CLOUDFLARE
    }

    /**
     * Set the storage backend preference.
     */
    suspend fun setUseCloudflareWorker(useCloudflare: Boolean) {
        context.storagePreferences.edit { preferences ->
            preferences[USE_CLOUDFLARE_WORKER] = useCloudflare
        }
    }

    /**
     * Get the current preference synchronously (for Hilt factory use).
     * This reads from cache, so prefer the Flow version when possible.
     */
    suspend fun isUsingCloudflareWorker(): Boolean {
        var result = DEFAULT_USE_CLOUDFLARE
        context.storagePreferences.data.collect { preferences ->
            result = preferences[USE_CLOUDFLARE_WORKER] ?: DEFAULT_USE_CLOUDFLARE
        }
        return result
    }
}
