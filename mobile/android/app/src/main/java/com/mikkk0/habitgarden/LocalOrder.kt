package com.mikkk0.habitgarden

import android.content.Context
import org.json.JSONArray

/** Per-device order in SharedPreferences, never in SQLite. */
class LocalOrder(context: Context) {
    private val prefs = context.getSharedPreferences("card_order", Context.MODE_PRIVATE)

    fun sorted(tasks: List<Habit>): List<Habit> {
        val byId = tasks.associateBy(Habit::id)
        val saved = ids()
        val savedSet = saved.toSet()
        return tasks.filter { it.id !in savedSet } + saved.mapNotNull(byId::get)
    }

    fun save(tasks: List<Habit>) {
        prefs.edit().putString("ids", JSONArray(tasks.map(Habit::id)).toString()).apply()
    }

    private fun ids(): List<Long> = try {
        val array = JSONArray(prefs.getString("ids", "[]"))
        (0 until array.length()).map(array::getLong).distinct()
    } catch (_: Exception) {
        emptyList()
    }
}
