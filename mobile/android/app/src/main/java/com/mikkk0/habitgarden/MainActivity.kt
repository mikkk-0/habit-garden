package com.mikkk0.habitgarden

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.app.TimePickerDialog
import android.content.ActivityNotFoundException
import android.content.ClipData
import android.content.Intent
import android.content.pm.PackageManager
import android.content.res.ColorStateList
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.text.InputFilter
import android.view.DragEvent
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.WindowInsets
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.PopupMenu
import android.widget.ProgressBar
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import java.time.LocalDate
import java.time.LocalTime
import java.time.YearMonth
import java.time.format.DateTimeFormatter
import java.util.Locale

class MainActivity : Activity() {
    private lateinit var store: HabitStore
    private lateinit var order: LocalOrder
    private lateinit var scheduler: ReminderScheduler
    private lateinit var emojiCatalog: EmojiCatalog
    private var archivedTab = false
    private var draggedId: Long? = null
    private val russian = Locale.forLanguageTag("ru")
    private val shortDate = DateTimeFormatter.ofPattern("d MMM yyyy", russian)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        store = HabitStore(this)
        order = LocalOrder(this)
        scheduler = ReminderScheduler(this, store)
        emojiCatalog = EmojiCatalog(this)
        render()
        if (Build.VERSION.SDK_INT >= 33 && !notificationsAllowed()) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 100)
        }
    }

    override fun onResume() {
        super.onResume()
        if (::scheduler.isInitialized) {
            scheduler.rescheduleAll()
            render()
        }
    }

    override fun onDestroy() {
        store.close()
        super.onDestroy()
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 100) {
            scheduler.rescheduleAll()
            render()
        }
    }

    private fun notificationsAllowed(): Boolean = Build.VERSION.SDK_INT < 33 ||
        checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED

    private fun render() {
        val all = order.sorted(store.all())
        val active = all.filterNot(Habit::archived)
        val visible = all.filter { it.archived == archivedTab }
        val done = active.count { store.isCompleted(it.id, LocalDate.now()) }
        val page = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(Ui.dp(this@MainActivity, 20), Ui.dp(this@MainActivity, 16), Ui.dp(this@MainActivity, 20), Ui.dp(this@MainActivity, 32))
        }
        val scroll = ScrollView(this).apply {
            isFillViewport = true
            setBackgroundColor(Ui.BACKGROUND)
            addView(page)
        }
        setContentView(scroll)
        if (Build.VERSION.SDK_INT >= 35) {
            scroll.setOnApplyWindowInsetsListener { view, insets ->
                val bars = insets.getInsets(WindowInsets.Type.systemBars())
                view.setPadding(0, bars.top, 0, bars.bottom)
                insets
            }
        }

        val brand = Ui.label(this, "🌿  сад привычек", 18f, Ui.GREEN, true)
        page.addView(brand)
        page.addView(spacer(30))
        page.addView(Ui.label(this, "МАЛЕНЬКИЕ ШАГИ КАЖДЫЙ ДЕНЬ", 10f, Ui.MUTED, true))
        page.addView(spacer(7))
        page.addView(Ui.label(this, "Расти в своём ритме.", 30f, Ui.INK, true))
        page.addView(spacer(6))
        page.addView(Ui.label(this, LocalDate.now().format(DateTimeFormatter.ofPattern("EEEE, d MMMM", russian)), 14f, Ui.MUTED))
        page.addView(spacer(22))

        val progressCard = column(Ui.GREEN_LIGHT, 18).apply { setPadding(Ui.dp(this@MainActivity, 18), Ui.dp(this@MainActivity, 16), Ui.dp(this@MainActivity, 18), Ui.dp(this@MainActivity, 16)) }
        progressCard.addView(Ui.label(this, "Сегодня выполнено", 12f, Ui.GREEN, true))
        progressCard.addView(Ui.label(this, "$done / ${active.size}", 28f, Ui.INK, true))
        progressCard.addView(ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal).apply {
            max = maxOf(1, active.size)
            progress = done
            progressTintList = ColorStateList.valueOf(Ui.GREEN)
            progressBackgroundTintList = ColorStateList.valueOf(0xFFD2DED0.toInt())
        })
        page.addView(progressCard)
        page.addView(spacer(18))

        if (!notificationsAllowed()) {
            page.addView(permissionBanner("Разрешите уведомления, чтобы получать напоминания.", "Разрешить") {
                if (Build.VERSION.SDK_INT >= 33) requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 100)
            })
        }
        if (Build.VERSION.SDK_INT >= 31 && !scheduler.exactAllowed()) {
            page.addView(permissionBanner("Для напоминаний точно в выбранное время разрешите точные будильники. Без разрешения Android может задержать уведомление.", "Настроить") {
                try {
                    startActivity(Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM, Uri.parse("package:$packageName")))
                } catch (_: ActivityNotFoundException) {
                    startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:$packageName")))
                }
            })
        }

        val tabs = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        tabs.addView(tab("Мои задания  ${active.size}", !archivedTab) { archivedTab = false; render() }, LinearLayout.LayoutParams(0, Ui.dp(this, 44), 1f))
        tabs.addView(tab("Архив  ${all.size - active.size}", archivedTab) { archivedTab = true; render() }, LinearLayout.LayoutParams(0, Ui.dp(this, 44), 1f))
        page.addView(tabs)
        page.addView(spacer(12))
        if (!archivedTab) {
            page.addView(actionText("＋  Новое задание") { _ -> showEditor(null) })
            page.addView(spacer(10))
        }
        page.addView(Ui.label(this, "Коснитесь карточки, чтобы изменить отметку. Зажмите ⠿ для перемещения.", 11f, Ui.MUTED))
        page.addView(spacer(14))
        if (visible.isEmpty()) {
            page.addView(Ui.label(this, if (archivedTab) "Архив пока пуст" else "Здесь скоро появятся привычки", 17f, Ui.MUTED, true))
        } else {
            visible.forEach { habit ->
                page.addView(card(habit, visible), LinearLayout.LayoutParams(-1, -2).apply { bottomMargin = Ui.dp(this@MainActivity, 12) })
            }
        }
    }

    private fun card(habit: Habit, visible: List<Habit>): LinearLayout {
        val done = store.isCompleted(habit.id, LocalDate.now())
        val stats = HabitMath.stats(habit.createdOn, store.completedDates(habit.id), LocalDate.now())
        val card = column(Ui.CARD, 18, Ui.BORDER).apply { setPadding(Ui.dp(this@MainActivity, 17), Ui.dp(this@MainActivity, 15), Ui.dp(this@MainActivity, 17), Ui.dp(this@MainActivity, 16)) }
        val top = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        val emoji = Ui.label(this, habit.emoji, 26f).apply {
            gravity = Gravity.CENTER
            alpha = if (done) 1f else 0.43f
            background = Ui.rounded(this@MainActivity, if (done) Ui.GREEN_LIGHT else 0xFFF0F1EA.toInt(), 13)
        }
        top.addView(emoji, LinearLayout.LayoutParams(Ui.dp(this, 48), Ui.dp(this, 48)))
        top.addView(View(this), LinearLayout.LayoutParams(0, 1, 1f))
        val handle = Ui.label(this, "⠿", 25f, Ui.MUTED).apply {
            gravity = Gravity.CENTER
            contentDescription = "Изменить порядок: ${habit.name}"
            setOnClickListener { showMoveMenu(this, habit, visible) }
            setOnLongClickListener {
                draggedId = habit.id
                val clip = ClipData.newPlainText("habit-id", habit.id.toString())
                startDragAndDrop(clip, View.DragShadowBuilder(card), null, 0)
                true
            }
        }
        top.addView(handle, LinearLayout.LayoutParams(Ui.dp(this, 42), Ui.dp(this, 42)))
        val menu = Ui.label(this, "···", 23f, Ui.MUTED).apply {
            gravity = Gravity.CENTER
            contentDescription = "Календарь и настройки: ${habit.name}"
            setOnClickListener { showEditor(habit) }
        }
        top.addView(menu, LinearLayout.LayoutParams(Ui.dp(this, 42), Ui.dp(this, 42)))
        card.addView(top)
        card.addView(spacer(14))
        card.addView(Ui.label(this, habit.name, 18f, Ui.INK, true))
        card.addView(spacer(18))
        val numbers = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        listOf("${stats.streak}" to "стрик, дней", "${stats.totalDays}" to "всего дней", "${stats.percent}%" to "выполнено").forEach { (value, label) ->
            val item = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
            item.addView(Ui.label(this, value, 18f, Ui.GREEN, true))
            item.addView(Ui.label(this, label, 10f, Ui.MUTED))
            numbers.addView(item, LinearLayout.LayoutParams(0, -2, 1f))
        }
        card.addView(numbers)
        card.addView(spacer(15))
        card.addView(ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal).apply {
            max = 100; progress = stats.percent
            progressTintList = ColorStateList.valueOf(Ui.GREEN)
            progressBackgroundTintList = ColorStateList.valueOf(0xFFE9EDE6.toInt())
        })
        card.addView(spacer(9))
        card.addView(Ui.label(this, "с ${habit.createdOn.format(shortDate)}  ·  ${if (done) "сделано сегодня" else "не сделано сегодня"}", 11f, if (done) Ui.GREEN else Ui.MUTED))
        card.setOnClickListener {
            if (habit.archived) showEditor(habit)
            else {
                store.setCompleted(habit.id, LocalDate.now(), !done)
                scheduler.schedule(habit.id)
                render()
            }
        }
        card.setOnDragListener { _, event ->
            when (event.action) {
                DragEvent.ACTION_DRAG_STARTED -> draggedId != null
                DragEvent.ACTION_DRAG_ENTERED -> { if (draggedId != habit.id) card.background = Ui.rounded(this, Ui.GREEN_LIGHT, 18, Ui.GREEN); true }
                DragEvent.ACTION_DRAG_EXITED, DragEvent.ACTION_DRAG_ENDED -> { card.background = Ui.rounded(this, Ui.CARD, 18, Ui.BORDER); if (event.action == DragEvent.ACTION_DRAG_ENDED) draggedId = null; true }
                DragEvent.ACTION_DROP -> {
                    val source = draggedId
                    if (source != null && source != habit.id) moveCard(source, habit.id, event.y > card.height / 2f)
                    true
                }
                else -> true
            }
        }
        return card
    }

    private fun showMoveMenu(anchor: View, habit: Habit, visible: List<Habit>) {
        val index = visible.indexOfFirst { it.id == habit.id }
        val popup = PopupMenu(this, anchor)
        popup.menu.add(0, 1, 0, "В начало")
        popup.menu.add(0, 2, 1, "Выше")
        popup.menu.add(0, 3, 2, "Ниже")
        popup.menu.add(0, 4, 3, "В конец")
        popup.setOnMenuItemClickListener { item ->
            when (item.itemId) {
                1 -> visible.firstOrNull()?.let { moveCard(habit.id, it.id, false) }
                2 -> visible.getOrNull(index - 1)?.let { moveCard(habit.id, it.id, false) }
                3 -> visible.getOrNull(index + 1)?.let { moveCard(habit.id, it.id, true) }
                4 -> visible.lastOrNull()?.let { moveCard(habit.id, it.id, true) }
            }
            true
        }
        popup.show()
    }

    private fun moveCard(sourceId: Long, targetId: Long, after: Boolean) {
        val all = order.sorted(store.all())
        val source = all.find { it.id == sourceId } ?: return
        val target = all.find { it.id == targetId } ?: return
        val moved = OrderMath.move(all, source, target, after)
        if (moved != all) { order.save(moved); render() }
    }

    private fun showEditor(original: Habit?) {
        val habit = original?.let { store.get(it.id) }
        var chosenEmoji = habit?.emoji ?: "🌱"
        var chosenTime = habit?.reminderTime ?: LocalTime.of(20, 0)
        var month = YearMonth.now()
        val form = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(Ui.dp(this@MainActivity, 20), Ui.dp(this@MainActivity, 8), Ui.dp(this@MainActivity, 20), Ui.dp(this@MainActivity, 8)) }
        val name = EditText(this).apply {
            hint = "Название задания"
            setText(habit?.name.orEmpty())
            isSingleLine = true
            filters = arrayOf(InputFilter.LengthFilter(80))
        }
        form.addView(Ui.label(this, "Название", 12f, Ui.MUTED, true))
        form.addView(name)
        form.addView(spacer(14))
        val emojiButton = actionText("$chosenEmoji  Выбрать эмодзи") { button ->
            emojiCatalog.choose { selected -> chosenEmoji = selected; button.text = "$selected  Выбрать эмодзи" }
        }
        form.addView(Ui.label(this, "Эмодзи задания", 12f, Ui.MUTED, true))
        form.addView(emojiButton)
        form.addView(spacer(14))
        val timeButton = actionText("Напомнить в ${chosenTime.format(DateTimeFormatter.ofPattern("HH:mm"))}") { button ->
            TimePickerDialog(this, { _, hour, minute ->
                chosenTime = LocalTime.of(hour, minute)
                button.text = "Напомнить в ${chosenTime.format(DateTimeFormatter.ofPattern("HH:mm"))}"
            }, chosenTime.hour, chosenTime.minute, true).show()
        }
        form.addView(timeButton)
        val archive = CheckBox(this).apply { text = "В архиве"; isChecked = habit?.archived ?: false }
        if (habit != null) {
            form.addView(spacer(12))
            form.addView(archive)
            form.addView(spacer(14))
            val calendar = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
            form.addView(calendar)
            fun drawCalendar() {
                calendar.removeAllViews()
                val heading = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
                val previous = Ui.label(this, "‹", 30f, Ui.GREEN).apply { gravity = Gravity.CENTER; setOnClickListener { month = month.minusMonths(1); drawCalendar() } }
                heading.addView(previous, LinearLayout.LayoutParams(Ui.dp(this, 42), Ui.dp(this, 42)))
                heading.addView(Ui.label(this, month.atDay(1).format(DateTimeFormatter.ofPattern("LLLL yyyy", russian)), 16f, Ui.INK, true), LinearLayout.LayoutParams(0, -2, 1f))
                val next = Ui.label(this, "›", 30f, Ui.GREEN).apply { gravity = Gravity.CENTER; setOnClickListener { month = month.plusMonths(1); drawCalendar() } }
                heading.addView(next, LinearLayout.LayoutParams(Ui.dp(this, 42), Ui.dp(this, 42)))
                calendar.addView(heading)
                val dates = store.completedDates(habit.id)
                val offset = month.atDay(1).dayOfWeek.value - 1
                val weeks = (offset + month.lengthOfMonth() + 6) / 7
                val today = LocalDate.now()
                val names = listOf("ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС")
                for (week in -1 until weeks) {
                    val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
                    for (column in 0..6) {
                        val index = week * 7 + column - offset + 1
                        val date = if (week >= 0 && index in 1..month.lengthOfMonth()) month.atDay(index) else null
                        val before = date != null && date.isBefore(habit.createdOn)
                        val future = date != null && date.isAfter(today)
                        val completed = date != null && date in dates
                        val cell = Ui.label(this, if (week == -1) names[column] else date?.dayOfMonth?.toString().orEmpty(), if (week == -1) 10f else 13f,
                            if (before || future) 0xFFB9C0B7.toInt() else if (completed) Ui.GREEN else Ui.INK, completed).apply {
                            gravity = Gravity.CENTER
                            if (week >= 0 && date != null) background = Ui.rounded(this@MainActivity,
                                if (before) 0xFFE9EBE6.toInt() else if (completed) 0xFFD9EBD8.toInt() else Ui.CARD, 8)
                            if (date != null && !before && !future && !habit.archived) setOnClickListener {
                                store.setCompleted(habit.id, date, !completed)
                                scheduler.schedule(habit.id)
                                render()
                                drawCalendar()
                            }
                        }
                        row.addView(cell, LinearLayout.LayoutParams(0, Ui.dp(this, if (week == -1) 28 else 41), 1f).apply { setMargins(Ui.dp(this@MainActivity, 2), Ui.dp(this@MainActivity, 2), Ui.dp(this@MainActivity, 2), Ui.dp(this@MainActivity, 2)) })
                    }
                    calendar.addView(row)
                }
                calendar.addView(Ui.label(this, "Серым — дни до создания. Нажмите на день, чтобы изменить отметку.", 11f, Ui.MUTED))
            }
            drawCalendar()
        }
        val scroll = ScrollView(this).apply { addView(form) }
        val dialog = AlertDialog.Builder(this)
            .setTitle(if (habit == null) "Новое задание" else "Календарь и настройки")
            .setView(scroll)
            .setNegativeButton("Закрыть", null)
            .setPositiveButton("Сохранить", null)
            .create()
        dialog.setOnShowListener {
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener {
                val cleanName = name.text.toString().trim()
                if (cleanName.isEmpty()) { name.error = "Введите название"; return@setOnClickListener }
                if (!emojiCatalog.contains(chosenEmoji)) { Toast.makeText(this, "Выберите эмодзи из списка", Toast.LENGTH_SHORT).show(); return@setOnClickListener }
                if (habit == null) {
                    val created = store.create(cleanName, chosenEmoji, chosenTime)
                    scheduler.schedule(created.id)
                } else {
                    store.update(habit.id, cleanName, chosenEmoji, chosenTime, archive.isChecked)
                    scheduler.schedule(habit.id)
                }
                dialog.dismiss()
                render()
            }
        }
        dialog.show()
    }

    private fun permissionBanner(message: String, button: String, action: () -> Unit): LinearLayout = column(Ui.GREEN_LIGHT, 14).apply {
        setPadding(Ui.dp(this@MainActivity, 14), Ui.dp(this@MainActivity, 12), Ui.dp(this@MainActivity, 14), Ui.dp(this@MainActivity, 12))
        addView(Ui.label(this@MainActivity, message, 12f, Ui.GREEN))
        addView(actionText(button) { _ -> action() })
        layoutParams = LinearLayout.LayoutParams(-1, -2).apply { bottomMargin = Ui.dp(this@MainActivity, 10) }
    }

    private fun tab(title: String, selected: Boolean, action: () -> Unit): TextView = Ui.label(this, title, 13f, if (selected) Ui.GREEN else Ui.MUTED, selected).apply {
        gravity = Gravity.CENTER
        background = Ui.rounded(this@MainActivity, if (selected) Ui.GREEN_LIGHT else Ui.BACKGROUND, 10)
        setOnClickListener { action() }
    }

    private fun actionText(title: String, action: (TextView) -> Unit): TextView = Ui.label(this, title, 14f, Ui.GREEN, true).apply {
        gravity = Gravity.CENTER
        background = Ui.rounded(this@MainActivity, Ui.GREEN_LIGHT, 10)
        setPadding(Ui.dp(this@MainActivity, 12), Ui.dp(this@MainActivity, 10), Ui.dp(this@MainActivity, 12), Ui.dp(this@MainActivity, 10))
        setOnClickListener { action(this) }
    }

    private fun column(color: Int, radius: Int, border: Int? = null): LinearLayout = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL
        background = Ui.rounded(this@MainActivity, color, radius, border)
    }

    private fun spacer(height: Int): View = View(this).apply { layoutParams = ViewGroup.LayoutParams(1, Ui.dp(this@MainActivity, height)) }
}
