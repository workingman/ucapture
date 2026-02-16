package ca.dgbi.ucapture.ui.navigation

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import ca.dgbi.ucapture.ui.recording.RecordingScreen
import ca.dgbi.ucapture.ui.settings.SettingsScreen
import ca.dgbi.ucapture.ui.timeline.TimelineScreen

/**
 * Sealed class representing app navigation routes
 */
sealed class Route(val path: String, val label: String, val icon: ImageVector) {
    data object Recording : Route("recording", "Recording", Icons.Default.Home)
    data object Timeline : Route("timeline", "Timeline", Icons.AutoMirrored.Filled.List)
    data object Settings : Route("settings", "Settings", Icons.Default.Settings)

    companion object {
        val bottomNavItems = listOf(Recording, Timeline, Settings)
    }
}

/**
 * Main navigation host for the app
 */
@Composable
fun AppNavHost(
    navController: NavHostController,
    modifier: Modifier = Modifier
) {
    NavHost(
        navController = navController,
        startDestination = Route.Recording.path,
        modifier = modifier
    ) {
        composable(Route.Recording.path) {
            RecordingScreen()
        }

        composable(Route.Timeline.path) {
            TimelineScreen()
        }

        composable(Route.Settings.path) {
            SettingsScreen(navController = navController)
        }
    }
}

/**
 * Bottom navigation bar for the app
 */
@Composable
fun AppBottomNavigation(
    navController: NavHostController,
    modifier: Modifier = Modifier
) {
    NavigationBar(modifier = modifier) {
        val navBackStackEntry by navController.currentBackStackEntryAsState()
        val currentDestination = navBackStackEntry?.destination

        Route.bottomNavItems.forEach { route ->
            NavigationBarItem(
                icon = { Icon(route.icon, contentDescription = route.label) },
                label = { Text(route.label) },
                selected = currentDestination?.hierarchy?.any { it.route == route.path } == true,
                onClick = {
                    navController.navigate(route.path) {
                        // Pop up to the start destination of the graph to
                        // avoid building up a large stack of destinations
                        // on the back stack as users select items
                        popUpTo(navController.graph.findStartDestination().id) {
                            saveState = true
                        }
                        // Avoid multiple copies of the same destination when
                        // reselecting the same item
                        launchSingleTop = true
                        // Restore state when reselecting a previously selected item
                        restoreState = true
                    }
                }
            )
        }
    }
}

