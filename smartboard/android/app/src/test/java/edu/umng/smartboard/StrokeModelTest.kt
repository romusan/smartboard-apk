package edu.umng.smartboard

import edu.umng.smartboard.model.BoardPoint
import edu.umng.smartboard.model.Stroke
import org.junit.Assert.assertEquals
import org.junit.Test

class StrokeModelTest {
    @Test fun normalizedPointIsStored() {
        val stroke = Stroke(points = listOf(BoardPoint(0.5f, 0.25f, 0.8f, 10L)))
        assertEquals(0.5f, stroke.points.first().x)
        assertEquals("page-1", stroke.page_id)
    }
}
