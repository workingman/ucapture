package ca.dgbi.ucapture.util

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.PowerManager
import android.provider.Settings

/**
 * Utilities for managing power/battery optimization settings.
 *
 * Android's battery optimization (Doze mode) can interrupt long-running
 * background operations. For reliable audio recording, the app should
 * request exemption from battery optimization.
 */
object PowerUtils {

    /**
     * Checks if the app is exempt from battery optimization.
     *
     * @param context Application context
     * @return true if app is ignoring battery optimizations
     */
    fun isIgnoringBatteryOptimizations(context: Context): Boolean {
        val powerManager = context.getSystemService(Context.POWER_SERVICE) as PowerManager
        return powerManager.isIgnoringBatteryOptimizations(context.packageName)
    }

    /**
     * Creates an intent to request battery optimization exemption.
     *
     * This opens the system settings where the user can manually
     * allow the app to ignore battery optimizations.
     *
     * Note: The direct REQUEST_IGNORE_BATTERY_OPTIMIZATIONS intent
     * may be restricted by Google Play policies for some app categories.
     * This method uses the safer approach of opening the settings page.
     *
     * @param context Application context
     * @return Intent to open battery optimization settings for this app
     */
    fun createBatteryOptimizationSettingsIntent(context: Context): Intent {
        return Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
            data = Uri.parse("package:${context.packageName}")
        }
    }

    /**
     * Creates an intent to open the app's detailed battery settings.
     *
     * Use this as a fallback if the direct exemption request doesn't work.
     *
     * @param context Application context
     * @return Intent to open app battery settings
     */
    fun createAppBatterySettingsIntent(context: Context): Intent {
        return Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
            data = Uri.parse("package:${context.packageName}")
        }
    }

    /**
     * Checks if the device is currently in Doze mode (idle).
     *
     * @param context Application context
     * @return true if device is in idle/Doze mode
     */
    fun isDeviceIdle(context: Context): Boolean {
        val powerManager = context.getSystemService(Context.POWER_SERVICE) as PowerManager
        return powerManager.isDeviceIdleMode
    }

    /**
     * Checks if the device is in power save mode (battery saver).
     *
     * @param context Application context
     * @return true if battery saver is enabled
     */
    fun isPowerSaveMode(context: Context): Boolean {
        val powerManager = context.getSystemService(Context.POWER_SERVICE) as PowerManager
        return powerManager.isPowerSaveMode
    }
}
