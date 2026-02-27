package ca.dgbi.ucapture

import android.app.Application
import androidx.hilt.work.HiltWorkerFactory
import androidx.work.Configuration
import ca.dgbi.ucapture.data.remote.UploadScheduler
import dagger.hilt.android.HiltAndroidApp
import kotlinx.coroutines.MainScope
import javax.inject.Inject

@HiltAndroidApp
class UCaptureApplication : Application(), Configuration.Provider {

    @Inject
    lateinit var workerFactory: HiltWorkerFactory

    @Inject
    lateinit var uploadScheduler: UploadScheduler

    private val applicationScope = MainScope()

    override fun onCreate() {
        super.onCreate()
        uploadScheduler.setupPeriodicRetry()
        uploadScheduler.setupPeriodicCleanup()
        uploadScheduler.schedulePendingUploads(applicationScope)
        uploadScheduler.runStartupCleanup(applicationScope)
    }

    override val workManagerConfiguration: Configuration
        get() = Configuration.Builder()
            .setWorkerFactory(workerFactory)
            .build()
}
