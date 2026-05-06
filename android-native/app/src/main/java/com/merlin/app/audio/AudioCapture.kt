package com.merlin.app.audio

import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.FileOutputStream

class AudioCapture {

    private var recorder: AudioRecord? = null
    private var isRecording = false

    companion object {
        private const val SAMPLE_RATE = 16000
        private const val CHANNEL_CONFIG = AudioFormat.CHANNEL_IN_MONO
        private const val AUDIO_FORMAT = AudioFormat.ENCODING_PCM_16BIT
    }

    suspend fun capture(durationMs: Int = 5000): ByteArray = withContext(Dispatchers.IO) {
        val bufferSize = AudioRecord.getMinBufferSize(SAMPLE_RATE, CHANNEL_CONFIG, AUDIO_FORMAT)
        val record = AudioRecord(
            MediaRecorder.AudioSource.MIC,
            SAMPLE_RATE, CHANNEL_CONFIG, AUDIO_FORMAT,
            bufferSize
        )

        if (record.state != AudioRecord.STATE_INITIALIZED) {
            return@withContext ByteArray(0)
        }

        val totalSamples = SAMPLE_RATE * durationMs / 1000
        val buffer = ShortArray(bufferSize / 2)
        val output = ByteArrayOutputStream()

        record.startRecording()
        isRecording = true
        var samplesRead = 0

        while (samplesRead < totalSamples && isRecording) {
            val read = record.read(buffer, 0, buffer.size)
            if (read > 0) {
                val bytes = ShortArrayToByteArray(buffer.copyOf(read))
                output.write(bytes)
                samplesRead += read
            }
        }

        record.stop()
        record.release()
        isRecording = false
        recorder = null

        output.toByteArray()
    }

    fun stop() {
        isRecording = false
        recorder?.stop()
        recorder?.release()
        recorder = null
    }

    private fun ShortArrayToByteArray(shorts: ShortArray): ByteArray {
        val bytes = ByteArray(shorts.size * 2)
        for (i in shorts.indices) {
            bytes[i * 2] = (shorts[i].toInt() and 0xFF).toByte()
            bytes[i * 2 + 1] = (shorts[i].toInt() shr 8 and 0xFF).toByte()
        }
        return bytes
    }
}
