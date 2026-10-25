package com.mikkk0.habitgarden

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import java.time.LocalDateTime

class ReminderReceiver : BroadcastReceiver() {
    companion object {
        const val ACTION = "com.mikkk0.habitgarden.REMIND"
        const val EXTRA_ID = "habit_id"
        private const val CHANNEL = "daily_habits"
    }

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != ACTION) return
        val id = intent.getLongExtra(EXTRA_ID, -1)
        if (id < 0) return
        HabitStore(context).use { store ->
            val scheduler = ReminderScheduler(context, store)
            if (Build.VERSION.SDK_INT >= 33 && context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                scheduler.schedule(id, skipToday = true)
                return
            }
            if (store.claimReminder(id, LocalDateTime.now())) {
                val habit = store.get(id)
                if (habit != null) notify(context, habit)
            }
            scheduler.schedule(id)
        }
    }

    private fun notify(context: Context, habit: Habit) {
        val manager = context.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel(CHANNEL, "Ежедневные привычки", NotificationManager.IMPORTANCE_DEFAULT))
        val open = PendingIntent.getActivity(
            context, 0, Intent(context, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val notification = Notification.Builder(context, CHANNEL)
            .setSmallIcon(R.drawable.ic_leaf)
            .setContentTitle("Время для привычки")
            .setContentText("${habit.emoji} ${habit.name} ещё не выполнено сегодня")
            .setContentIntent(open)
            .setAutoCancel(true)
            .build()
        manager.notify(habit.id.toInt(), notification)
    }
}
