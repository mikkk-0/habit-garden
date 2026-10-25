package com.mikkk0.habitgarden

import android.app.AlarmManager
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneId

/** PendingIntent alarms survive removal from Recents; no service or polling loop runs. */
class ReminderScheduler(private val context: Context, private val store: HabitStore) {
    private val manager = context.getSystemService(AlarmManager::class.java)

    fun exactAllowed(): Boolean = Build.VERSION.SDK_INT < 31 || manager.canScheduleExactAlarms()

    fun rescheduleAll() {
        store.all().forEach { schedule(it.id) }
    }

    fun schedule(id: Long, skipToday: Boolean = false) {
        val intent = pendingIntent(id)
        manager.cancel(intent)
        val habit = store.get(id) ?: return
        val now = LocalDateTime.now()
        val done = store.isCompleted(id, LocalDate.now())
        if (habit.archived || done) context.getSystemService(NotificationManager::class.java).cancel(id.toInt())
        val next = ReminderPlan.next(habit, now, done, skipToday) ?: return
        val millis = next.atZone(ZoneId.systemDefault()).toInstant().toEpochMilli()
        try {
            if (exactAllowed()) manager.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, millis, intent)
            else manager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, millis, intent)
        } catch (_: SecurityException) {
            manager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, millis, intent)
        }
    }

    private fun pendingIntent(id: Long): PendingIntent {
        val intent = Intent(context, ReminderReceiver::class.java).apply {
            action = ReminderReceiver.ACTION
            putExtra(ReminderReceiver.EXTRA_ID, id)
        }
        return PendingIntent.getBroadcast(
            context, id.toInt(), intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }
}
