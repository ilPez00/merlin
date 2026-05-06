package com.merlin.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.merlin.app.config.ConfigStore
import com.merlin.app.ui.SetupScreen
import com.merlin.app.ui.SettingsScreen
import com.merlin.app.ui.VisorScreen
import com.merlin.app.ui.theme.MerlinColorScheme
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    private lateinit var configStore: ConfigStore

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        configStore = ConfigStore(applicationContext)

        setContent {
            androidx.compose.material3.MaterialTheme(
                colorScheme = MerlinColorScheme
            ) {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = Color.Black
                ) {
                    val navController = rememberNavController()
                    val scope = rememberCoroutineScope()

                    NavHost(
                        navController = navController,
                        startDestination = "setup"
                    ) {
                        composable("setup") {
                            SetupScreen(
                                onContinue = { provider, apiKey, baseUrl ->
                                    scope.launch {
                                        configStore.setApiKey(apiKey)
                                        configStore.setProvider(provider)
                                        if (baseUrl.isNotBlank()) configStore.setBaseUrl(baseUrl)
                                    }
                                    navController.navigate("visor") {
                                        popUpTo("setup") { inclusive = true }
                                    }
                                }
                            )
                        }

                        composable("visor") {
                            VisorScreen(
                                configStore = configStore,
                                onOpenSettings = {
                                    navController.navigate("settings")
                                }
                            )
                        }

                        composable("settings") {
                            SettingsScreen(
                                configStore = configStore,
                                onBack = { navController.popBackStack() }
                            )
                        }
                    }
                }
            }
        }
    }
}
