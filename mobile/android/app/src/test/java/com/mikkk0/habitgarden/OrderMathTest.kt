package com.mikkk0.habitgarden

import org.junit.Assert.assertEquals
import org.junit.Test

class OrderMathTest {
    @Test fun movesCardsBeforeAndAfterTargets() {
        assertEquals(listOf(3, 1, 2), OrderMath.move(listOf(1, 2, 3), 3, 1, false))
        assertEquals(listOf(2, 3, 1), OrderMath.move(listOf(1, 2, 3), 1, 3, true))
    }

    @Test fun ignoresMissingOrSameCards() {
        val cards = listOf(1, 2, 3)
        assertEquals(cards, OrderMath.move(cards, 1, 1, false))
        assertEquals(cards, OrderMath.move(cards, 4, 2, false))
    }
}
