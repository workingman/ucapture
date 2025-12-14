# uCapture Session Notes

## Project
Android audio recording app with GPS/calendar metadata, Google Drive upload.

**Package:** `ca.dgbi.ucapture`
**Stack:** Kotlin, Jetpack Compose, MVVM, Room, Hilt, WorkManager
**SDK:** min 29, target 35, compile 36

## Status
| Task | Status |
|------|--------|
| 1.0 Project setup | Complete |
| 2.0 Audio recording service | Complete |
| 3.0 Metadata collection | Complete |
| 4.0 Local storage (Room) | Complete |
| 5.0 Google Drive integration | **Partial** - auth works, upload has token persistence bug |
| 6.0 UI | Complete |

## Current Issue: Upload Worker Token Persistence

**Problem:** UploadWorker returns RETRY because access token is stored in memory only.

- `GoogleDriveAuthManager` stores `accessToken` as a class variable
- WorkManager runs workers in different context where token isn't available
- Worker checks `isSignedIn()` which requires token, fails, returns RETRY

**Fix needed:** Persist access token securely (EncryptedSharedPreferences or DataStore with encryption).

## What's Working
- Google Sign-In via Credential Manager
- Drive authorization (gets access token)
- Folder creation/selection in Drive
- Recording with chunking (1-min chunks for testing)
- Chunks emit to completedChunks flow
- WorkManager schedules upload jobs
- UI shows pending upload count

## Google OAuth Setup (Complete)
- Google Cloud Console project configured
- Drive API enabled
- OAuth consent screen with `drive.file` scope
- Web Client ID in `local.properties`: `GOOGLE_WEB_CLIENT_ID=741090335587-n423313itvauv8cn0jtsi70c3jhidlu0.apps.googleusercontent.com`
- Android Client ID configured with SHA-1 fingerprint

## Testing Notes
- Chunk duration set to 1 minute for testing (ChunkManager.kt lines 40-41)
- TODO comments mark values to restore for production (30min default, 5min minimum)

## Key Files Modified This Session
```
data/remote/GoogleDriveAuthManager.kt  # Auth flow with AuthorizationRequest
data/remote/GoogleDriveStorage.kt      # findOrCreateFolder(), logging
ui/settings/SettingsScreen.kt          # Folder name input dialog
ui/settings/SettingsViewModel.kt       # createOrSelectFolder()
service/ChunkManager.kt                # Chunk duration (1 min for testing)
gradle/libs.versions.toml              # Added coroutines-play-services
app/build.gradle.kts                   # BuildConfig for client ID
```

## Next Steps
1. **Fix token persistence** - Store access token in EncryptedSharedPreferences
2. **Test full upload flow** - Verify files appear in Drive folder
3. **Restore chunk duration** - Change back to 30 min for production
4. **Handle token refresh** - Access tokens expire, need refresh logic

## Commands
```bash
cd /Users/gwr/Documents/dev/ubiq-capture/android
./gradlew build
./gradlew installDebug
adb -s 48131FDAQ003B8 logcat -d | grep -iE "ucapture|upload|drive"
```

## Tests
- 109 unit tests (76 original + 33 for UI ViewModels)
- Some test file lint issues (Kotlin tooling bug, not blocking)

---
**Updated:** 2025-12-13
