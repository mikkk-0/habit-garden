package com.mikkk0.habitgarden

object OrderMath {
    fun <T> move(items: List<T>, from: T, target: T, after: Boolean): List<T> {
        if (from == target || from !in items || target !in items) return items
        val result = items.toMutableList()
        result.remove(from)
        result.add(result.indexOf(target) + if (after) 1 else 0, from)
        return result
    }
}
