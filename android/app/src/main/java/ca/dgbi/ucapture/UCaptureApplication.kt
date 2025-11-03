package ca.dgbi.ucapture

import android.app.Application
import dagger.hilt.android.HiltAndroidApp

@HiltAndroidApp
class UCaptureApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        // Application initialization will go here
    }
}
