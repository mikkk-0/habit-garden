package com.mikkk0.habitgarden

import android.content.ContentValues
import android.content.Context
import android.database.Cursor
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import java.time.LocalDate
import java.time.LocalTime

/** The database stores habits and completed days only; presentation order is elsewhere. */
class HabitStore(context: Context) : SQLiteOpenHelper(context, "habits.db", null, 1) {
    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL("""CREATE TABLE habits (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            created_on TEXT NOT NULL,
            archived INTEGER NOT NULL DEFAULT 0,
            emoji TEXT NOT NULL DEFAULT '🌱',
            reminder_time TEXT NOT NULL DEFAULT '20:00',
            last_notified_on TEXT
        )""")
        db.execSQL("""CREATE TABLE completions (
            habit_id INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
            day TEXT NOT NULL,
            PRIMARY KEY (habit_id, day)
        ) WITHOUT ROWID""")
    }

    override fun onConfigure(db: SQLiteDatabase) {
        super.onConfigure(db)
        db.setForeignKeyConstraintsEnabled(true)
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        // Add explicit migrations here before increasing the schema version.
    }

    @Synchronized fun all(): List<Habit> = readableDatabase.rawQuery(
        "SELECT id, name, created_on, archived, emoji, reminder_time, last_notified_on FROM habits ORDER BY id DESC", null
    ).use { cursor -> buildList { while (cursor.moveToNext()) add(cursor.habit()) } }

    @Synchronized fun get(id: Long): Habit? = readableDatabase.rawQuery(
        "SELECT id, name, created_on, archived, emoji, reminder_time, last_notified_on FROM habits WHERE id = ?",
        arrayOf(id.toString()),
    ).use { cursor -> if (cursor.moveToFirst()) cursor.habit() else null }

    @Synchronized fun create(name: String, emoji: String, reminderTime: LocalTime): Habit {
        val cleanName = name.trim()
        require(cleanName.isNotEmpty() && cleanName.length <= 80)
        val values = ContentValues().apply {
            put("name", cleanName)
            put("created_on", LocalDate.now().toString())
            put("emoji", emoji)
            put("reminder_time", reminderTime.toString())
        }
        val id = writableDatabase.insertOrThrow("habits", null, values)
        return requireNotNull(get(id))
    }

    @Synchronized fun update(id: Long, name: String, emoji: String, reminderTime: LocalTime, archived: Boolean) {
        val cleanName = name.trim()
        require(cleanName.isNotEmpty() && cleanName.length <= 80)
        val values = ContentValues().apply {
            put("name", cleanName)
            put("emoji", emoji)
            put("reminder_time", reminderTime.toString())
            put("archived", if (archived) 1 else 0)
        }
        require(writableDatabase.update("habits", values, "id = ?", arrayOf(id.toString())) == 1)
    }

    @Synchronized fun completedDates(id: Long, through: LocalDate = LocalDate.now()): Set<LocalDate> =
        readableDatabase.rawQuery(
            "SELECT day FROM completions WHERE habit_id = ? AND day <= ?",
            arrayOf(id.toString(), through.toString()),
        ).use { cursor -> buildSet { while (cursor.moveToNext()) add(LocalDate.parse(cursor.getString(0))) } }

    @Synchronized fun isCompleted(id: Long, day: LocalDate): Boolean = readableDatabase.rawQuery(
        "SELECT 1 FROM completions WHERE habit_id = ? AND day = ? LIMIT 1",
        arrayOf(id.toString(), day.toString()),
    ).use { it.moveToFirst() }

    @Synchronized fun setCompleted(id: Long, day: LocalDate, completed: Boolean) {
        val habit = requireNotNull(get(id))
        require(!habit.archived && !day.isBefore(habit.createdOn) && !day.isAfter(LocalDate.now()))
        if (completed) {
            val values = ContentValues().apply { put("habit_id", id); put("day", day.toString()) }
            writableDatabase.insertWithOnConflict("completions", null, values, SQLiteDatabase.CONFLICT_IGNORE)
        } else {
            writableDatabase.delete("completions", "habit_id = ? AND day = ?", arrayOf(id.toString(), day.toString()))
        }
    }

    /** Return true once per day, even when two alarms arrive close together. */
    @Synchronized fun claimReminder(id: Long, now: java.time.LocalDateTime): Boolean {
        val db = writableDatabase
        db.beginTransaction()
        try {
            val habit = get(id) ?: return false
            val day = now.toLocalDate()
            if (habit.archived || day.isBefore(habit.createdOn) || now.toLocalTime().isBefore(habit.reminderTime) ||
                habit.lastNotifiedOn == day || isCompleted(id, day)) return false
            val values = ContentValues().apply { put("last_notified_on", day.toString()) }
            db.update("habits", values, "id = ?", arrayOf(id.toString()))
            db.setTransactionSuccessful()
            return true
        } finally {
            db.endTransaction()
        }
    }

    private fun Cursor.habit(): Habit = Habit(
        getLong(0), getString(1), LocalDate.parse(getString(2)), getInt(3) != 0,
        getString(4), LocalTime.parse(getString(5)), getString(6)?.let(LocalDate::parse),
    )
}
