package com.mikkk0.habitgarden

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate

class HabitMathTest {
    private val today = LocalDate.of(2026, 10, 25)

    @Test fun creationDayCountsAsFirstDay() {
        val stats = HabitMath.stats(today, setOf(today), today)
        assertEquals(1L, stats.totalDays)
        assertEquals(100, stats.percent)
        assertEquals(1, stats.streak)
        assertTrue(stats.completedToday)
    }

    @Test fun yesterdayStreakContinuesUntilTodayIsMissed() {
        val created = today.minusDays(4)
        val done = setOf(today.minusDays(3), today.minusDays(2), today.minusDays(1))
        val stats = HabitMath.stats(created, done, today)
        assertEquals(5L, stats.totalDays)
        assertEquals(60, stats.percent)
        assertEquals(3, stats.streak)
        assertFalse(stats.completedToday)
        assertEquals(0, HabitMath.stats(created, done - today.minusDays(1), today).streak)
    }

    @Test fun ignoresDatesOutsideLifetime() {
        val stats = HabitMath.stats(today.minusDays(1), setOf(today.minusDays(5), today.plusDays(1)), today)
        assertEquals(0, stats.completedDays)
        assertEquals(0, stats.percent)
    }
}
