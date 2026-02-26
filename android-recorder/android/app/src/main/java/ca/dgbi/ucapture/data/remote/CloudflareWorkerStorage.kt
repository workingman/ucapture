package ca.dgbi.ucapture.data.remote

import android.content.Context
import android.util.Log
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.io.OutputStream
import java.net.HttpURLConnection
import java.net.URL
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Uploads recordings to the Cloudflare Worker audio-processing pipeline.
 *
 * POST /v1/upload — multipart/form-data with audio file + metadata JSON.
 * Authorization: Bearer <google_oauth_access_token>
 *
 * On success the Worker returns HTTP 202 with a JSON body:
 *   { "batch_id": "...", "status": "uploaded", "message": "..." }
 *
 * The returned batch_id is stored in [UploadResult.batchId] and persisted to
 * Room so the app can later poll /v1/status/{batch_id} for transcript availability.
 */
@Singleton
class CloudflareWorkerStorage @Inject constructor(
    @ApplicationContext private val context: Context,
    private val authManager: GoogleDriveAuthManager
) : CloudStorageProvider {

    companion object {
        private const val TAG = "CFWorkerStorage"
        private const val BASE_URL = "https://audio-processor.geoff-ec6.workers.dev"
        private const val BOUNDARY = "uCaptureBoundary7MA4YWxkTrZu0gW"
        private const val CONNECT_TIMEOUT_MS = 30_000
        private const val READ_TIMEOUT_MS = 120_000
    }

    override val providerId = "cloudflare_worker"

    override suspend fun isAuthenticated(): Boolean = authManager.isSignedIn()

    // Not applicable for the CF Worker — no folder concept.
    override suspend fun getTargetFolderId(): String? = null
    override suspend fun setTargetFolderId(folderId: String) {}

    // MD5 verification not supported by the Worker. Return true so the upload
    // flow in UploadWorker completes normally.
    override suspend fun verifyUpload(fileId: String, expectedMd5: String): Boolean = true

    // Deletion via the Worker API is not yet implemented.
    override suspend fun delete(fileId: String): Boolean = false

    // No folder hierarchy for the CF Worker.
    override suspend fun listFolders(parentId: String?): List<CloudFolder> = emptyList()

    override suspend fun upload(
        audioFile: File,
        metadataFile: File?,
        folderId: String?
    ): UploadResult = withContext(Dispatchers.IO) {
        authManager.ensureFreshToken()

        val token = authManager.getAccessToken()
            ?: return@withContext UploadResult(
                success = false,
                error = UploadError.NotAuthenticated
            )

        val result = executeUpload(audioFile, metadataFile, token)

        // Retry once if the server rejected our token.
        if (result.error is UploadError.NotAuthenticated && authManager.refreshToken()) {
            val freshToken = authManager.getAccessToken()
                ?: return@withContext UploadResult(
                    success = false,
                    error = UploadError.NotAuthenticated
                )
            executeUpload(audioFile, metadataFile, freshToken)
        } else {
            result
        }
    }

    private suspend fun executeUpload(
        audioFile: File,
        metadataFile: File?,
        token: String
    ): UploadResult = withContext(Dispatchers.IO) {
        val connection = (URL("$BASE_URL/v1/upload").openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            doOutput = true
            setChunkedStreamingMode(8192)
            connectTimeout = CONNECT_TIMEOUT_MS
            readTimeout = READ_TIMEOUT_MS
            setRequestProperty("Authorization", "Bearer $token")
            setRequestProperty("Content-Type", "multipart/form-data; boundary=$BOUNDARY")
        }

        try {
            connection.outputStream.buffered().use { output ->
                writeTextPart(output, "priority", "normal")
                writeFilePart(output, "audio", audioFile.name, audioFile, "audio/mp4")
                if (metadataFile != null && metadataFile.exists()) {
                    writeFilePart(output, "metadata", "metadata.json", metadataFile, "application/json")
                }
                output.write("--$BOUNDARY--\r\n".toByteArray())
                output.flush()
            }

            val responseCode = connection.responseCode
            return@withContext when {
                responseCode == 202 -> {
                    val body = connection.inputStream.use { it.readBytes().toString(Charsets.UTF_8) }
                    val json = JSONObject(body)
                    val batchId = if (json.has("batch_id")) json.getString("batch_id") else null
                    Log.d(TAG, "Upload accepted: batch_id=$batchId")
                    UploadResult(success = true, audioFileId = batchId, batchId = batchId)
                }
                responseCode == 401 || responseCode == 403 -> {
                    Log.w(TAG, "Auth failure: HTTP $responseCode")
                    UploadResult(success = false, error = UploadError.NotAuthenticated)
                }
                else -> {
                    val errorBody = readErrorBody(connection)
                    Log.w(TAG, "Upload failed: HTTP $responseCode — $errorBody")
                    UploadResult(
                        success = false,
                        error = UploadError.ApiError(responseCode, "HTTP $responseCode")
                    )
                }
            }
        } catch (e: IOException) {
            Log.e(TAG, "Upload IO error", e)
            UploadResult(success = false, error = UploadError.NetworkError)
        } catch (e: Exception) {
            Log.e(TAG, "Upload error", e)
            UploadResult(success = false, error = UploadError.ApiError(0, e.message ?: "Unknown"))
        } finally {
            connection.disconnect()
        }
    }

    // ------------------------------------------------------------------------------------------
    // Multipart helpers
    // ------------------------------------------------------------------------------------------

    private fun writeTextPart(output: OutputStream, name: String, value: String) {
        output.write("--$BOUNDARY\r\n".toByteArray())
        output.write("Content-Disposition: form-data; name=\"$name\"\r\n".toByteArray())
        output.write("\r\n".toByteArray())
        output.write(value.toByteArray())
        output.write("\r\n".toByteArray())
    }

    private fun writeFilePart(
        output: OutputStream,
        name: String,
        filename: String,
        file: File,
        contentType: String
    ) {
        output.write("--$BOUNDARY\r\n".toByteArray())
        output.write(
            "Content-Disposition: form-data; name=\"$name\"; filename=\"$filename\"\r\n".toByteArray()
        )
        output.write("Content-Type: $contentType\r\n".toByteArray())
        output.write("\r\n".toByteArray())
        file.inputStream().use { it.copyTo(output) }
        output.write("\r\n".toByteArray())
    }

    private fun readErrorBody(connection: HttpURLConnection): String = try {
        connection.errorStream?.use { it.readBytes().toString(Charsets.UTF_8) } ?: ""
    } catch (e: Exception) {
        ""
    }
}
