package com.merlin.app.camera

import android.content.Context
import android.util.Base64
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.ImageProxy
import androidx.core.content.ContextCompat

class FrameCapture(private val context: Context) {

    interface OnFrameCaptured {
        fun onSuccess(base64: String)
        fun onError(message: String)
    }

    private var imageCapture: ImageCapture? = null

    fun bind(imageCapture: ImageCapture) {
        this.imageCapture = imageCapture
    }

    fun capture(callback: OnFrameCaptured) {
        imageCapture?.takePicture(
            ContextCompat.getMainExecutor(context),
            object : ImageCapture.OnImageCapturedCallback() {
                override fun onCaptureSuccess(image: ImageProxy) {
                    val buffer = image.planes[0].buffer
                    val bytes = ByteArray(buffer.remaining())
                    buffer.get(bytes)
                    val b64 = Base64.encodeToString(bytes, Base64.NO_WRAP)
                    callback.onSuccess(b64)
                    image.close()
                }

                override fun onError(exception: ImageCaptureException) {
                    callback.onError(exception.message ?: "Capture failed")
                }
            }
        )
    }
}
