# Add project specific ProGuard rules here.
# You can control the set of applied configuration files using the
# proguardFiles setting in build.gradle.
#
# For more details, see
#   http://developer.android.com/guide/developing/tools/proguard.html

# Preserve line numbers for debugging stack traces
-keepattributes SourceFile,LineNumberTable

# Hilt
-keep class dagger.hilt.** { *; }
-keep class javax.inject.** { *; }
-keep class * extends dagger.hilt.android.internal.managers.ComponentSupplier { *; }
-keep @dagger.hilt.android.HiltAndroidApp class * { *; }
-keep @dagger.hilt.android.AndroidEntryPoint class * { *; }

# Room
-keep class * extends androidx.room.RoomDatabase { *; }
-keep @androidx.room.Entity class * { *; }
-keep @androidx.room.Dao interface * { *; }

# Google Drive API / HTTP Client
-keep class com.google.api.** { *; }
-dontwarn com.google.api.**
-dontwarn org.apache.http.**
-dontwarn com.google.common.**

# Coroutines
-keepclassmembers class kotlinx.coroutines.** { volatile <fields>; }

# Keep app data models for Room and serialization
-keep class ca.dgbi.ucapture.data.model.** { *; }
