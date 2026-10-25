package com.mikkk0.habitgarden

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime

class ReminderPlanTest {
    private val day = LocalDate.of(2026, 10, 25)
    private val habit = Habit(7, "Читать", day.minusDays(1), false, "📚", LocalTime.of(20, 0), null)

    @Test fun schedulesChosenTimeBeforeItArrives() {
        assertEquals(day.atTime(20, 0), ReminderPlan.next(habit, day.atTime(19, 0), false))
    }

    @Test fun missedReminderIsDueSoon() {
        val now = day.atTime(21, 0)
        assertEquals(now.plusSeconds(2), ReminderPlan.next(habit, now, false))
    }

    @Test fun completedOrAlreadyNotifiedWaitsUntilTomorrow() {
        val now = day.atTime(21, 0)
        assertEquals(day.plusDays(1).atTime(20, 0), ReminderPlan.next(habit, now, true))
        assertEquals(day.plusDays(1).atTime(20, 0), ReminderPlan.next(habit.copy(lastNotifiedOn = day), now, false))
        assertEquals(day.plusDays(1).atTime(20, 0), ReminderPlan.next(habit, now, false, skipToday = true))
    }

    @Test fun archivedHabitHasNoAlarm() {
        assertNull(ReminderPlan.next(habit.copy(archived = true), LocalDateTime.of(day, LocalTime.NOON), false))
    }
}
