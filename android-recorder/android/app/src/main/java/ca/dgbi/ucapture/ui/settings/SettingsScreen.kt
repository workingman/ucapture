package ca.dgbi.ucapture.ui.settings

import android.app.Activity
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.Switch
import androidx.compose.material3.TextButton
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.TextField
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavHostController

/**
 * Settings screen for uCapture.
 *
 * Manages Google Drive authentication and folder selection.
 */
@Composable
fun SettingsScreen(
    navController: NavHostController,
    viewModel: SettingsViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val activity = LocalContext.current as Activity

    var showFolderDialog by remember { mutableStateOf(false) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Text(
            text = "Settings",
            style = MaterialTheme.typography.headlineMedium,
            modifier = Modifier.padding(bottom = 8.dp)
        )

        StorageBackendSection(
            useCloudflareWorker = uiState.useCloudflareWorker,
            onToggle = { viewModel.toggleStorageBackend(it) }
        )

        GoogleDriveSection(
            isSignedIn = uiState.isSignedIn,
            userEmail = uiState.userEmail,
            currentFolderName = uiState.currentFolderName,
            isLoading = uiState.isLoading,
            errorMessage = uiState.errorMessage,
            onSignIn = { viewModel.signIn(activity) },
            onSignOut = { viewModel.signOut() },
            onSelectFolder = { showFolderDialog = true }
        )
    }

    if (showFolderDialog) {
        FolderInputDialog(
            currentFolderName = uiState.currentFolderName,
            isLoading = uiState.isLoading,
            onDismiss = { showFolderDialog = false },
            onConfirm = { folderName ->
                viewModel.createOrSelectFolder(folderName)
                showFolderDialog = false
            }
        )
    }
}

/**
 * Storage backend selection showing Cloudflare Worker vs Google Drive.
 */
@Composable
private fun StorageBackendSection(
    useCloudflareWorker: Boolean,
    onToggle: (Boolean) -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text(
                text = "Upload Backend",
                style = MaterialTheme.typography.titleLarge
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = if (useCloudflareWorker) "Cloudflare Worker" else "Google Drive",
                        style = MaterialTheme.typography.bodyLarge
                    )
                    Text(
                        text = if (useCloudflareWorker)
                            "Recommended — uploads to cloud processor"
                        else
                            "Fallback — uploads to Google Drive",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                Spacer(modifier = Modifier.width(16.dp))
                Switch(
                    checked = useCloudflareWorker,
                    onCheckedChange = onToggle
                )
            }
        }
    }
}

/**
 * Google Drive section showing authentication status and folder picker.
 */
@Composable
private fun GoogleDriveSection(
    isSignedIn: Boolean,
    userEmail: String?,
    currentFolderName: String?,
    isLoading: Boolean,
    errorMessage: String?,
    onSignIn: () -> Unit,
    onSignOut: () -> Unit,
    onSelectFolder: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text(
                text = "Google Drive",
                style = MaterialTheme.typography.titleLarge
            )

            if (isLoading) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.Center,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    CircularProgressIndicator()
                }
            } else if (isSignedIn) {
                // Signed in state
                Text(
                    text = "Signed in as:",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Text(
                    text = userEmail ?: "Unknown",
                    style = MaterialTheme.typography.bodyLarge
                )

                Spacer(modifier = Modifier.height(8.dp))

                // Folder selection
                OutlinedButton(
                    onClick = onSelectFolder,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Icon(
                        imageVector = Icons.Default.Settings,
                        contentDescription = null,
                        modifier = Modifier.padding(end = 8.dp)
                    )
                    Column(
                        modifier = Modifier.weight(1f),
                        horizontalAlignment = Alignment.Start
                    ) {
                        Text(
                            text = currentFolderName ?: "Select folder",
                            style = MaterialTheme.typography.bodyMedium
                        )
                        if (currentFolderName == null) {
                            Text(
                                text = "No folder selected",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                }

                // Show error message if any
                if (errorMessage != null) {
                    Text(
                        text = errorMessage,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                        modifier = Modifier.padding(horizontal = 4.dp)
                    )
                }

                Spacer(modifier = Modifier.height(8.dp))

                // Sign out button
                TextButton(
                    onClick = onSignOut,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("Sign out")
                }
            } else {
                // Not signed in
                Text(
                    text = "Sign in to enable cloud backup",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )

                OutlinedButton(
                    onClick = onSignIn,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("Sign in with Google")
                }
            }
        }
    }
}

/**
 * Dialog for entering or creating a Google Drive folder.
 *
 * With the drive.file scope, we can only access folders created by this app.
 * This dialog allows users to enter a folder name, which will be created if it doesn't exist.
 */
@Composable
private fun FolderInputDialog(
    currentFolderName: String?,
    isLoading: Boolean,
    onDismiss: () -> Unit,
    onConfirm: (String) -> Unit
) {
    var folderName by remember { mutableStateOf(currentFolderName ?: "uCapture") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Text("Select Drive folder")
        },
        text = {
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Text(
                    text = "Enter a folder name. The folder will be created in your Google Drive if it doesn't exist.",
                    style = MaterialTheme.typography.bodyMedium
                )

                TextField(
                    value = folderName,
                    onValueChange = { folderName = it },
                    label = { Text("Folder name") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                    enabled = !isLoading
                )

                if (isLoading) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.Center,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        CircularProgressIndicator()
                    }
                }
            }
        },
        confirmButton = {
            TextButton(
                onClick = { onConfirm(folderName.trim()) },
                enabled = !isLoading && folderName.trim().isNotEmpty()
            ) {
                Text("OK")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("Cancel")
            }
        }
    )
}
