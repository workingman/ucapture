package ca.dgbi.ucapture.data.local

import androidx.room.TypeConverter
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken

/**
 * Room type converters for complex types.
 */
class Converters {
    private val gson = Gson()

    @TypeConverter
    fun fromStringList(list: List<String>?): String? =
        list?.let { gson.toJson(it) }

    @TypeConverter
    fun toStringList(json: String?): List<String>? =
        json?.let {
            gson.fromJson(it, object : TypeToken<List<String>>() {}.type)
        }
}
