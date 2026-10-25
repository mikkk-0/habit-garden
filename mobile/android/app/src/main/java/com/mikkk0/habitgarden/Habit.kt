package com.mikkk0.habitgarden

import java.time.LocalDate
import java.time.LocalTime
import java.time.temporal.ChronoUnit

data class Habit(
    val id: Long,
    val name: String,
    val createdOn: LocalDate,
    val archived: Boolean,
    val emoji: String,
    val reminderTime: LocalTime,
    val lastNotifiedOn: LocalDate?,
)

data class HabitStats(
    val totalDays: Long,
    val completedDays: Int,
    val percent: Int,
    val streak: Int,
    val completedToday: Boolean,
)

object HabitMath {
    fun stats(createdOn: LocalDate, completed: Set<LocalDate>, today: LocalDate): HabitStats {
        val total = maxOf(1L, ChronoUnit.DAYS.between(createdOn, today) + 1)
        val valid = completed.filter { !it.isBefore(createdOn) && !it.isAfter(today) }.toSet()
        val doneToday = today in valid
        var cursor = if (doneToday) today else today.minusDays(1)
        var streak = 0
        while (!cursor.isBefore(createdOn) && cursor in valid) {
            streak++
            cursor = cursor.minusDays(1)
        }
        return HabitStats(total, valid.size, kotlin.math.round(valid.size * 100.0 / total).toInt(), streak, doneToday)
    }
}
