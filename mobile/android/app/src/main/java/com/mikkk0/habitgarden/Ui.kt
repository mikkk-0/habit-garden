package com.mikkk0.habitgarden

import android.content.Context
import android.graphics.drawable.GradientDrawable
import android.view.Gravity
import android.widget.TextView

object Ui {
    val BACKGROUND = 0xFFF5F3ED.toInt()
    val CARD = 0xFFFFFEFA.toInt()
    val INK = 0xFF244037.toInt()
    val GREEN = 0xFF315B42.toInt()
    val GREEN_LIGHT = 0xFFE3EEE0.toInt()
    val MUTED = 0xFF8FA092.toInt()
    val BORDER = 0xFFE1E6DB.toInt()

    fun dp(context: Context, size: Int): Int = (size * context.resources.displayMetrics.density + 0.5f).toInt()

    fun rounded(context: Context, color: Int, radius: Int, border: Int? = null): GradientDrawable =
        GradientDrawable().apply {
            setColor(color)
            cornerRadius = dp(context, radius).toFloat()
            if (border != null) setStroke(dp(context, 1), border)
        }

    fun label(context: Context, value: String, size: Float, color: Int = INK, bold: Boolean = false): TextView =
        TextView(context).apply {
            text = value
            textSize = size
            setTextColor(color)
            if (bold) typeface = android.graphics.Typeface.DEFAULT_BOLD
            gravity = Gravity.CENTER_VERTICAL
        }
}
