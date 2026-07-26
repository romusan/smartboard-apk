package edu.umng.smartboard.ai

import com.google.android.gms.tasks.Task
import com.google.mlkit.common.model.DownloadConditions
import com.google.mlkit.common.model.RemoteModelManager
import com.google.mlkit.vision.digitalink.DigitalInk
import com.google.mlkit.vision.digitalink.DigitalInkRecognition
import com.google.mlkit.vision.digitalink.DigitalInkRecognitionModel
import com.google.mlkit.vision.digitalink.DigitalInkRecognitionModelIdentifier
import com.google.mlkit.vision.digitalink.DigitalInkRecognizer
import com.google.mlkit.vision.digitalink.DigitalInkRecognizerOptions
import edu.umng.smartboard.model.Stroke
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlin.coroutines.suspendCoroutine

class HandwritingRecognizer(languageTag: String = "es") {
    private val model: DigitalInkRecognitionModel
    private val recognizer: DigitalInkRecognizer
    private val modelManager = RemoteModelManager.getInstance()

    init {
        val identifier = DigitalInkRecognitionModelIdentifier.fromLanguageTag(languageTag)
            ?: error("No hay modelo de escritura para $languageTag")
        model = DigitalInkRecognitionModel.builder(identifier).build()
        recognizer = DigitalInkRecognition.getClient(
            DigitalInkRecognizerOptions.builder(model).build()
        )
    }

    suspend fun recognize(strokes: List<Stroke>): String = withContext(Dispatchers.IO) {
        if (strokes.isEmpty()) return@withContext ""
        ensureModelDownloaded()
        val ink = strokes.toDigitalInk()
        val result = recognizer.recognize(ink).await()
        result.candidates.firstOrNull()?.text.orEmpty()
    }

    private suspend fun ensureModelDownloaded() {
        val downloaded = modelManager.isModelDownloaded(model).await()
        if (!downloaded) {
            val conditions = DownloadConditions.Builder().build()
            modelManager.download(model, conditions).await()
        }
    }

    private fun List<Stroke>.toDigitalInk(): DigitalInk {
        val inkBuilder = DigitalInk.builder()
        forEach { boardStroke ->
            val strokeBuilder = DigitalInk.Stroke.builder()
            boardStroke.points.forEach { point ->
                strokeBuilder.addPoint(
                    DigitalInk.Point.create(
                        point.x * CANVAS_SCALE,
                        point.y * CANVAS_SCALE,
                        point.t
                    )
                )
            }
            inkBuilder.addStroke(strokeBuilder.build())
        }
        return inkBuilder.build()
    }

    private suspend fun <T> Task<T>.await(): T = suspendCoroutine { continuation ->
        addOnSuccessListener { continuation.resume(it) }
        addOnFailureListener { continuation.resumeWithException(it) }
    }

    companion object {
        private const val CANVAS_SCALE = 1000f
    }
}
