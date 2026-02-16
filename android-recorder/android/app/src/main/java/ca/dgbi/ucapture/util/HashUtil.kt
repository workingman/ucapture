package ca.dgbi.ucapture.util

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.security.MessageDigest

/**
 * Utility for MD5 hash calculation.
 *
 * Used for file integrity verification during cloud uploads.
 */
object HashUtil {

    /**
     * Calculate MD5 hash of a file.
     *
     * @param file The file to hash
     * @return MD5 hash as lowercase hex string, or null if file cannot be read
     */
    suspend fun md5(file: File): String? = withContext(Dispatchers.IO) {
        try {
            val digest = MessageDigest.getInstance("MD5")
            file.inputStream().use { fis ->
                val buffer = ByteArray(8192)
                var bytesRead: Int
                while (fis.read(buffer).also { bytesRead = it } != -1) {
                    digest.update(buffer, 0, bytesRead)
                }
            }
            digest.digest().toHexString()
        } catch (e: Exception) {
            null
        }
    }

    /**
     * Calculate MD5 hash of a byte array.
     *
     * @param bytes The bytes to hash
     * @return MD5 hash as lowercase hex string
     */
    fun md5(bytes: ByteArray): String {
        val digest = MessageDigest.getInstance("MD5")
        return digest.digest(bytes).toHexString()
    }

    /**
     * Verify file integrity against expected hash.
     *
     * @param file The file to verify
     * @param expectedHash The expected MD5 hash (case-insensitive)
     * @return true if hashes match, false otherwise
     */
    suspend fun verifyMd5(file: File, expectedHash: String): Boolean {
        val actualHash = md5(file) ?: return false
        return actualHash.equals(expectedHash, ignoreCase = true)
    }

    private fun ByteArray.toHexString(): String =
        joinToString("") { "%02x".format(it) }
}
