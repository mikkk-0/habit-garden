package com.mikkk0.habitgarden

import android.app.AlertDialog
import android.content.Context
import android.text.Editable
import android.text.TextWatcher
import android.view.Gravity
import android.view.View
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.EditText
import android.widget.GridLayout
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Spinner
import org.json.JSONObject
import java.util.Locale

data class EmojiOption(val symbol: String, val name: String, val keywords: String, val category: String)

class EmojiCatalog(private val context: Context) {
    val items: List<EmojiOption> by lazy {
        val json = JSONObject(context.assets.open("emoji-catalog.json").bufferedReader().use { it.readText() })
        val array = json.getJSONArray("items")
        (0 until array.length()).map { index ->
            val item = array.getJSONArray(index)
            EmojiOption(item.getString(0), item.getString(1), item.getString(2), item.getString(3))
        }
    }

    fun contains(symbol: String): Boolean = items.any { it.symbol == symbol }

    fun choose(onChosen: (String) -> Unit) {
        val categories = listOf(
            "Частые" to "favorites", "Смайлы" to "Smileys & Emotion", "Люди" to "People & Body",
            "Природа" to "Animals & Nature", "Еда" to "Food & Drink", "Места" to "Travel & Places",
            "Занятия" to "Activities", "Предметы" to "Objects", "Символы" to "Symbols", "Флаги" to "Flags",
        )
        val favorites = setOf("🌱", "📚", "💧", "🏃", "🧘", "💪", "🍎", "🥗", "☕", "🪥", "💊", "🛌", "🚶", "🚴", "✍️", "📝", "💻", "🎨", "🎸", "🎵", "🧹", "💰", "📅", "⏰", "❤️", "☀️", "🌙", "🌿", "🌸", "🐾", "🏠", "🧠", "🎯", "🔥", "⭐", "✅")
        val root = LinearLayout(context).apply { orientation = LinearLayout.VERTICAL; setPadding(Ui.dp(context, 18), Ui.dp(context, 8), Ui.dp(context, 18), 0) }
        val search = EditText(context).apply { hint = "Поиск эмодзи"; isSingleLine = true }
        val spinner = Spinner(context).apply {
            adapter = ArrayAdapter(context, android.R.layout.simple_spinner_dropdown_item, categories.map { it.first })
        }
        val grid = GridLayout(context).apply { columnCount = 4 }
        val more = Button(context).apply { text = "Показать ещё" }
        val scroll = ScrollView(context).apply { addView(grid) }
        root.addView(search)
        root.addView(spinner)
        root.addView(scroll, LinearLayout.LayoutParams(-1, Ui.dp(context, 310)))
        root.addView(more)
        val dialog = AlertDialog.Builder(context).setTitle("Выберите эмодзи").setView(root).setNegativeButton("Закрыть", null).create()
        var limit = 60
        fun render() {
            val query = search.text.toString().trim().lowercase(Locale.forLanguageTag("ru"))
            val selected = categories[spinner.selectedItemPosition.coerceAtLeast(0)].second
            val matches = items.filter {
                if (query.isNotEmpty()) "${it.symbol} ${it.name} ${it.keywords}".lowercase(Locale.forLanguageTag("ru")).contains(query)
                else if (selected == "favorites") it.symbol in favorites else it.category == selected
            }
            grid.removeAllViews()
            matches.take(limit).forEach { item ->
                val choice = Ui.label(context, item.symbol, 27f).apply {
                    gravity = Gravity.CENTER
                    contentDescription = item.name
                    background = Ui.rounded(context, Ui.CARD, 9)
                    setOnClickListener { onChosen(item.symbol); dialog.dismiss() }
                }
                grid.addView(choice, GridLayout.LayoutParams().apply {
                    width = Ui.dp(context, 48)
                    height = Ui.dp(context, 50)
                    setMargins(Ui.dp(context, 2), Ui.dp(context, 2), Ui.dp(context, 2), Ui.dp(context, 2))
                })
            }
            more.visibility = if (matches.size > limit) View.VISIBLE else View.GONE
        }
        search.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) = Unit
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) { limit = 60; render() }
            override fun afterTextChanged(s: Editable?) = Unit
        })
        spinner.onItemSelectedListener = object : android.widget.AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: android.widget.AdapterView<*>?, view: View?, position: Int, id: Long) { limit = 60; render() }
            override fun onNothingSelected(parent: android.widget.AdapterView<*>?) = Unit
        }
        more.setOnClickListener { limit += 60; render() }
        dialog.show()
        render()
    }
}
