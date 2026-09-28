package app.dsc.pulsar.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val PulsarColorScheme = darkColorScheme(
    primary = PulsarCyan,
    onPrimary = Color.Black,
    secondary = PulsarCyanDark,
    onSecondary = Color.Black,
    background = PulsarBackground,
    onBackground = PulsarTextPrimary,
    surface = PulsarSurface,
    onSurface = PulsarTextPrimary,
    surfaceVariant = PulsarCard,
    onSurfaceVariant = PulsarTextSecondary,
    outline = PulsarCardBorder
)

@Composable
fun PulsarAgentTheme(
    content: @Composable () -> Unit
) {
    MaterialTheme(
        colorScheme = PulsarColorScheme,
        typography = Typography,
        content = content
    )
}
