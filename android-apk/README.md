# Optional Android APK

This directory contains an isolated Capacitor wrapper for the existing
`hAI.highfishMP3zPlayer` frontend. The FastAPI backend, media files, indexes,
database, Docker services, and server-side configuration remain on the server
and are not copied into the APK.

## Repository suitability

The repository has a static Vanilla JavaScript player in `samba-player.html`,
with JavaScript modules and public icons/manifest files at the repository root.
The player already talks to the backend through HTTP API endpoints and can
therefore be hosted inside a WebView while the backend remains remote.

The repository landing page (`index.html`) is not used as the app entry point.
The build stages `samba-player.html` as `www/index.html`.

## Local build

Requirements: Node.js 20+, npm, Java 17+, Android SDK, and a Unix-compatible
shell for the build script.

```sh
cd android-apk
npm ci
npm run build:web
npx cap sync android
./android/gradlew --no-daemon assembleDebug
```

The debug APK is written to:

```text
android/app/build/outputs/apk/debug/app-debug.apk
```

No signing key is created or configured. This is a debug-only APK and is not
intended for Play Store distribution.

## GitHub Actions

`android-apk/.github/workflows/android-apk.yml` describes manual
`workflow_dispatch` runs and an optional automatic build when files under
`android-apk/` change. The workflow builds only the debug variant and uploads the APK as
`highfish-mp3zplayer-debug-apk` with 14 days of artifact retention.

GitHub only discovers Actions workflow files below the repository-root
`.github/workflows/` directory. The requested isolated location is therefore
kept under `android-apk/`, but it must be moved or mirrored to the repository
root before GitHub can execute it.

## Configuration and limitations

- Capacitor app ID: `de.highfishai.mp3zplayer`
- Capacitor web directory: `www`
- Only public frontend files are staged by `scripts/build-web.sh`.
- Backend URL, authentication, media storage, and database access remain
  server-side; the APK does not contain a backend or Docker container.
- The player must be configured to reach a deployed backend. A local
  `localhost` backend refers to the Android device, not the server.
- External Google Fonts remain external network resources and may be
  unavailable offline.
