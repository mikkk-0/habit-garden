package com.mikkk0.habitgarden

import java.time.LocalDateTime

object ReminderPlan {
    /** One alarm per habit. A missed reminder is due soon after the app returns. */
    fun next(habit: Habit, now: LocalDateTime, completedToday: Boolean, skipToday: Boolean = false): LocalDateTime? {
        if (habit.archived) return null
        val today = now.toLocalDate()
        val due = today.atTime(habit.reminderTime)
        if (skipToday || completedToday || habit.lastNotifiedOn == today) return due.plusDays(1)
        return if (due.isAfter(now)) due else now.plusSeconds(2)
    }
}
