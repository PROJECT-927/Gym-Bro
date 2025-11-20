import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/io.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:image/image.dart' as img;
import 'package:path_provider/path_provider.dart';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:open_file/open_file.dart';
// Ensure this import points to your actual translation file location
import 'package:frontend/translate.dart'; 
import 'package:flutter/services.dart'; // <--- ADD THIS LINE

// ============================================================================
// BACKGROUND ISOLATE FUNCTIONS (Top Level)
// ============================================================================

/// Processes the camera frame for the AI Backend
/// Resizes to 480px width to ensure speed and correct aspect ratio
String _processFrameOnIsolate(Map<String, dynamic> params) {
  try {
    final int width = params['width'];
    final int height = params['height'];
    final List<dynamic> planes = params['planes'];
    final String format = params['format'];

    img.Image? image;

    // 1. Convert YUV420 to RGB
    if (format == 'ImageFormatGroup.yuv420') {
      final yPlane = planes[0]['bytes'] as Uint8List;
      final uPlane = planes[1]['bytes'] as Uint8List;
      final vPlane = planes[2]['bytes'] as Uint8List;
      final uvRowStride = planes[1]['bytesPerRow'] as int;
      final uvPixelStride = 2;

      image = img.Image(width: width, height: height);

      for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
          final int uvIndex = (uvPixelStride * (x / 2).floor()) + (uvRowStride * (y / 2).floor());
          final int index = y * width + x;

          // Bounds check
          if (index >= yPlane.length || uvIndex >= uPlane.length || uvIndex >= vPlane.length) continue;

          final yp = yPlane[index];
          final up = uPlane[uvIndex];
          final vp = vPlane[uvIndex];

          int r = (yp + 1.402 * (vp - 128)).round();
          int g = (yp - 0.344136 * (up - 128) - 0.714136 * (vp - 128)).round();
          int b = (yp + 1.772 * (up - 128)).round();

          image.setPixelRgba(x, y, r.clamp(0, 255), g.clamp(0, 255), b.clamp(0, 255), 255);
        }
      }
    } else if (format == 'ImageFormatGroup.bgra8888') {
      final plane = planes[0]['bytes'] as Uint8List;
      image = img.Image.fromBytes(width: width, height: height, bytes: plane.buffer, order: img.ChannelOrder.bgra);
    }

    if (image == null) return "";

    // 2. CRITICAL: Resize for AI (MediaPipe is faster with small images)
    final img.Image smallImage = img.copyResize(image, width: 480);

    // 3. Encode to JPEG with reduced quality for speed
    final List<int> jpeg = img.encodeJpg(smallImage, quality: 60);
    final String base64Image = base64Encode(jpeg);

    // 4. Send the JSON
    final Map<String, dynamic> frameData = {
      'frame': base64Image,
      'width': smallImage.width, // Send new dimensions
      'height': smallImage.height,
    };

    return jsonEncode(frameData);
  } catch (e) {
    return "";
  }
}

/// Converts a specific frame to PNG for the PDF Report (High Quality)
Uint8List? _convertCameraImageToPng(Map<String, dynamic> imageParams) {
  try {
    final int width = imageParams['width'];
    final int height = imageParams['height'];
    final List<dynamic> planes = imageParams['planes'];
    final String format = imageParams['format'];

    img.Image? image;

    if (format == 'ImageFormatGroup.yuv420') {
      final yPlane = planes[0]['bytes'] as Uint8List;
      final uPlane = planes[1]['bytes'] as Uint8List;
      final vPlane = planes[2]['bytes'] as Uint8List;
      final uvRowStride = planes[1]['bytesPerRow'] as int;
      final uvPixelStride = 2;

      image = img.Image(width: width, height: height);

      for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
          final int uvIndex = (uvPixelStride * (x / 2).floor()) + (uvRowStride * (y / 2).floor());
          final int index = y * width + x;

          if (index >= yPlane.length || uvIndex >= uPlane.length || uvIndex >= vPlane.length) continue;

          final yp = yPlane[index];
          final up = uPlane[uvIndex];
          final vp = vPlane[uvIndex];

          int r = (yp + 1.402 * (vp - 128)).round();
          int g = (yp - 0.344136 * (up - 128) - 0.714136 * (vp - 128)).round();
          int b = (yp + 1.772 * (up - 128)).round();

          image.setPixelRgba(x, y, r.clamp(0, 255), g.clamp(0, 255), b.clamp(0, 255), 255);
        }
      }
    } else if (format == 'ImageFormatGroup.bgra8888') {
      final plane = planes[0]['bytes'] as Uint8List;
      image = img.Image.fromBytes(width: width, height: height, bytes: plane.buffer, order: img.ChannelOrder.bgra);
    }

    if (image == null) return null;

    // Rotate 270 degrees for front camera to be upright
    final img.Image rotatedImage = img.copyRotate(image, angle: 270);

    // Resize to a reasonable dimension for the PDF
    final img.Image resizedImage = img.copyResize(
      rotatedImage,
      width: 600,
      interpolation: img.Interpolation.linear,
    );

    return Uint8List.fromList(img.encodePng(resizedImage));
  } catch (e) {
    debugPrint("Error converting image in isolate: $e");
    return null;
  }
}

/// Generates the PDF in the background
Future<String?> _generatePdfInBackground(Map<String, dynamic> params) async {
  try {
    final String exerciseName = params['exerciseName'];
    final int reps = params['reps'];
    final String time = params['time'];
    final String savePath = params['savePath'];
    final List<Map<String, dynamic>> errorReportsData = List<Map<String, dynamic>>.from(params['errorReports']);

    // --- 3. Initialize the Font ---
    final Uint8List fontBytes = params['fontBytes'];
    final ttf = pw.Font.ttf(fontBytes.buffer.asByteData());

    final pdf = pw.Document(
      // --- 4. Set Default Theme with Custom Font ---
      theme: pw.ThemeData.withFont(
        base: ttf,
        bold: ttf, // Use the same font or a bold version if you have one
      ),
    );

    final String dateTime = DateTime.now().toLocal().toString().split('.')[0];

    // Title Page
    pdf.addPage(
      pw.Page(
        build: (pw.Context context) {
          return pw.Center(
            child: pw.Column(
              mainAxisAlignment: pw.MainAxisAlignment.center,
              children: [
                // Use style without manually setting font, as Theme handles it now
                pw.Text('Workout Report', style: pw.TextStyle(fontSize: 40, fontWeight: pw.FontWeight.bold)),
                pw.SizedBox(height: 20),
                pw.Text(exerciseName.toUpperCase(), style: const pw.TextStyle(fontSize: 24)),
                pw.SizedBox(height: 10),
                pw.Text(dateTime, style: const pw.TextStyle(fontSize: 18)),
                pw.SizedBox(height: 30),
                pw.Text('Total Reps: $reps', style: const pw.TextStyle(fontSize: 20)),
                pw.Text('Total Time: $time', style: const pw.TextStyle(fontSize: 20)),
                pw.SizedBox(height: 50),
                pw.Text(
                  errorReportsData.isEmpty ? 'No errors detected. Great job!' : 'Found ${errorReportsData.length} unique error(s).',
                  style: pw.TextStyle(
                    fontSize: 18,
                    // Font fallback logic in case color overrides needed
                    color: errorReportsData.isEmpty ? PdfColors.green : PdfColors.red,
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );

    // Error Pages
    for (final reportData in errorReportsData) {
      final String error = reportData['error'];
      final Uint8List imageBytes = reportData['imageBytes'];
      final List<String> timestamps = List<String>.from(reportData['timestamps']);
      final pdfImage = pw.MemoryImage(imageBytes);

      pdf.addPage(
        pw.Page(
          build: (pw.Context context) {
            return pw.Column(
              crossAxisAlignment: pw.CrossAxisAlignment.start,
              children: [
                // The Theme will apply the font here automatically
                pw.Text('ERROR: $error', style: pw.TextStyle(fontSize: 24, fontWeight: pw.FontWeight.bold, color: PdfColors.red)),
                pw.SizedBox(height: 20),
                pw.Center(
                  child: pw.Container(
                    constraints: const pw.BoxConstraints(maxHeight: 350, maxWidth: 400),
                    child: pw.Image(pdfImage, fit: pw.BoxFit.contain),
                  ),
                ),
                pw.SizedBox(height: 20),
                pw.Text('Occurred at:', style: pw.TextStyle(fontSize: 18, fontWeight: pw.FontWeight.bold)),
                pw.SizedBox(height: 10),
                pw.Wrap(
                  spacing: 8.0,
                  runSpacing: 4.0,
                  children: timestamps.map((time) {
                    return pw.Container(
                      padding: const pw.EdgeInsets.all(5),
                      decoration: pw.BoxDecoration(
                        color: PdfColors.grey200,
                        borderRadius: pw.BorderRadius.circular(5),
                      ),
                      child: pw.Text(time),
                    );
                  }).toList(),
                ),
              ],
            );
          },
        ),
      );
    }

    final File file = File(savePath);
    await file.writeAsBytes(await pdf.save());
    return savePath;
  } catch (e) {
    debugPrint('Error generating PDF in background: $e');
    return null;
  }
}
// ============================================================================
// MODELS
// ============================================================================

class WorkoutFeedback {
  final int reps;
  final String time;
  final String error;
  final String adjustment;
  final bool perfectRep;

  WorkoutFeedback({
    required this.reps,
    required this.time,
    required this.error,
    required this.adjustment,
    required this.perfectRep,
  });

  factory WorkoutFeedback.fromJson(Map<String, dynamic> json) {
    return WorkoutFeedback(
      reps: json['reps'] ?? 0,
      time: json['time'] ?? '00:00',
      error: json['error'] ?? '',
      adjustment: json['adjustment'] ?? '',
      perfectRep: json['perfect_rep'] ?? false,
    );
  }

  WorkoutFeedback copyWith({
    int? reps,
    String? time,
    String? error,
    String? adjustment,
    bool? perfectRep,
  }) {
    return WorkoutFeedback(
      reps: reps ?? this.reps,
      time: time ?? this.time,
      error: error ?? this.error,
      adjustment: adjustment ?? this.adjustment,
      perfectRep: perfectRep ?? this.perfectRep,
    );
  }

  WorkoutFeedback copyWithTime(String newTime) {
    return WorkoutFeedback(
      reps: reps,
      time: newTime,
      error: error,
      adjustment: adjustment,
      perfectRep: perfectRep,
    );
  }
}

class ErrorReport {
  final String error;
  final Uint8List firstImage;
  final List<String> timestamps;

  ErrorReport({
    required this.error,
    required this.firstImage,
    required this.timestamps,
  });
}

// ============================================================================
// MAIN SCREEN
// ============================================================================

class ExerciseWorkoutScreen extends StatefulWidget {
  final String exerciseName;
  final String languageCode; // Added for translation

  const ExerciseWorkoutScreen({
    super.key, 
    required this.exerciseName,
    required this.languageCode,
  });

  @override
  State<ExerciseWorkoutScreen> createState() => _ExerciseWorkoutScreenState();
}

class _ExerciseWorkoutScreenState extends State<ExerciseWorkoutScreen> {
  CameraController? _cameraController;
  WebSocketChannel? _channel;
  FlutterTts flutterTts = FlutterTts();

  WorkoutFeedback _currentFeedback = WorkoutFeedback(
    reps: 0,
    time: '00:00',
    error: '',
    adjustment: 'INITIALIZING...',
    perfectRep: false,
  );

  Timer? _workoutTimer;
  int _timeInSeconds = 0;
  bool _isProcessingFrame = false;

  Timer? _errorTimer;
  String _potentialError = "";
  String _stableError = "";
  String _lastSpokenError = "";

  // State variables for error reporting
  final Map<String, ErrorReport> _errorReports = {};
  CameraImage? _currentCameraImage;
  bool _isSavingReport = false;
  bool _isWorkoutEnding = false;

  // IMPORTANT: Update this IP to your backend
  final String _backendIpAddress = "100.100.121.79"; 
  final int _backendPort = 8765;

  @override
  void initState() {
    super.initState();
    _initializeCamera();
    _connectWebSocket();
    _startWorkoutTimer();
    _initializeTts();
  }

  @override
  void dispose() {
    _cameraController?.stopImageStream();
    _cameraController?.dispose();
    _channel?.sink.close();
    _workoutTimer?.cancel();
    _errorTimer?.cancel();
    flutterTts.stop();
    super.dispose();
  }

  Future<void> _initializeTts() async {
    // Uses the language code from the widget
    await flutterTts.setLanguage(
      AppTranslations.getTtsLocale(widget.languageCode),
    );
    await flutterTts.setSpeechRate(0.5);
    await flutterTts.setVolume(1.0);
    await flutterTts.setPitch(1.0);
  }

  Future<void> _speak(String text) async {
    if (text.isNotEmpty) {
      await flutterTts.speak(text);
    }
  }

  Future<void> _initializeCamera() async {
    final cameras = await availableCameras();
    if (cameras.isNotEmpty) {
      CameraDescription frontCamera;
      try {
        frontCamera = cameras.firstWhere(
              (camera) => camera.lensDirection == CameraLensDirection.front,
        );
      } catch (e) {
        debugPrint("No front camera found, using first available camera.");
        frontCamera = cameras[0];
      }

      _cameraController = CameraController(
        frontCamera,
        ResolutionPreset.high,
        enableAudio: false,
        imageFormatGroup: Platform.isAndroid
            ? ImageFormatGroup.yuv420
            : ImageFormatGroup.bgra8888,
      );

      try {
        await _cameraController!.initialize();
        if (mounted) {
          setState(() {});
          _startImageStream();
        }
      } on CameraException catch (e) {
        debugPrint("Camera Error: $e");
      }
    } else {
      debugPrint("No cameras available.");
    }
  }

  void _startImageStream() {
    _cameraController?.startImageStream((CameraImage image) {
      _currentCameraImage = image; // Keep full res for PDF

      if (_channel == null || _isProcessingFrame) {
        return;
      }
      _isProcessingFrame = true;

      // Prepare params (Pass ALL planes for proper color conversion)
      final imageParams = {
        'width': image.width,
        'height': image.height,
        'format': image.format.group.toString(),
        'planes': image.planes.map((p) => {
          'bytes': p.bytes,
          'bytesPerRow': p.bytesPerRow,
        }).toList(),
      };

      compute(_processFrameOnIsolate, imageParams).then((jsonString) {
        if (mounted && _channel != null && jsonString.isNotEmpty) {
          _channel!.sink.add(jsonString);
        }
        // Small delay to prevent flooding the network
        Future.delayed(const Duration(milliseconds: 50), () {
          _isProcessingFrame = false;
        });
      }).catchError((e) {
        debugPrint("Error in frame processing isolate: $e");
        _isProcessingFrame = false;
      });
    });
  }

  void _connectWebSocket() {
    try {
      final uri = Uri.parse('ws://${_backendIpAddress.trim()}:$_backendPort');
      _channel = IOWebSocketChannel.connect(uri);
      debugPrint("Attempting to connect to WebSocket: $uri");
      _channel!.sink.add(jsonEncode({'exercise': widget.exerciseName}));

      _channel!.stream.listen(
            (message) {
          if (mounted) {
            try {
              final Map<String, dynamic> data = jsonDecode(message);
              
              // 1. TRANSLATION LOGIC HERE
              String rawError = data['error'] ?? '';
              String rawAdjustment = data['adjustment'] ?? '';

              String displayError = AppTranslations.translate(
                rawError,
                widget.languageCode,
              );
              String displayAdjustment = AppTranslations.translate(
                rawAdjustment,
                widget.languageCode,
              );

              // 2. Create Feedback object with TRANSLATED text
              final WorkoutFeedback newFeedback = WorkoutFeedback(
                reps: data['reps'] ?? 0,
                time: _currentFeedback.time, // Keep local time
                error: displayError,
                adjustment: displayAdjustment,
                perfectRep: data['perfect_rep'] ?? false,
              );

              // 3. Error Logging & Screenshots
              // Note: We use the TRANSLATED error as the key, so the report shows the user's language
              final String newError = newFeedback.error;
              final String currentTime = newFeedback.time;

              if (newError.isNotEmpty && _currentCameraImage != null) {
                if (!_errorReports.containsKey(newError)) {
                  _captureErrorScreenshot(newError, currentTime, _currentCameraImage!);
                } else {
                  final lastTime = _errorReports[newError]!.timestamps.last;
                  if (currentTime != lastTime) {
                    setState(() {
                      _errorReports[newError]!.timestamps.add(currentTime);
                    });
                  }
                }
              }

              setState(() {
                _currentFeedback = newFeedback.copyWith(error: _stableError);
              });

              // 4. Stabilization & TTS
              if (newError != _potentialError) {
                _errorTimer?.cancel();
                _potentialError = newError;

                if (newError.isEmpty) {
                  setState(() {
                    _stableError = "";
                  });
                  _lastSpokenError = "";
                } else {
                  _errorTimer = Timer(const Duration(seconds: 2), () {
                    if (mounted && _potentialError == newError) {
                      setState(() {
                        _stableError = newError;
                      });
                      if (_stableError != _lastSpokenError) {
                        _speak(_stableError);
                        _lastSpokenError = _stableError;
                      }
                    }
                  });
                }
              }
            } catch (e) {
              debugPrint("Error processing WebSocket message: $e");
            }
          }
        },
        onDone: () {
          debugPrint('WebSocket connection closed!');
          _errorTimer?.cancel();
          if (_isWorkoutEnding || !mounted) return;
          setState(() {
            _stableError = 'CONNECTION LOST';
          });
          _speak("Connection Lost");
        },
        onError: (error) {
          debugPrint('WebSocket error: $error');
          _errorTimer?.cancel();
          if (!mounted) return;
          setState(() {
            _stableError = 'CONNECTION ERROR';
          });
          _speak("Connection Error");
        },
      );
    } catch (e) {
      debugPrint("WebSocket connection failed to establish: $e");
      if (mounted) {
        setState(() {
          _stableError = 'WS INIT FAILED';
        });
      }
    }
  }

  void _captureErrorScreenshot(String error, String time, CameraImage cameraImage) {
    final imageParams = {
      'width': cameraImage.width,
      'height': cameraImage.height,
      'planes': cameraImage.planes.map((p) => {
        'bytes': p.bytes,
        'bytesPerRow': p.bytesPerRow,
      }).toList(),
      'format': cameraImage.format.group.toString(),
    };

    compute(_convertCameraImageToPng, imageParams).then((pngBytes) {
      if (pngBytes != null && mounted) {
        setState(() {
          _errorReports[error] = ErrorReport(
            error: error,
            firstImage: pngBytes,
            timestamps: [time],
          );
        });
        debugPrint("Screenshot captured for error: $error");
      }
    }).catchError((e) {
      debugPrint("Error capturing screenshot: $e");
    });
  }

  void _startWorkoutTimer() {
    _workoutTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (mounted) {
        setState(() {
          _timeInSeconds++;
          int minutes = _timeInSeconds ~/ 60;
          int seconds = _timeInSeconds % 60;
          _currentFeedback = _currentFeedback.copyWith(
            time: '${minutes.toString().padLeft(2, '0')}:${seconds.toString().padLeft(2, '0')}',
          );
        });
      }
    });
  }

  Future<String?> _generateAndSavePdf() async {
    try {
      // 1. Select the correct font file based on the current language code
      String fontAssetPath;
      if (widget.languageCode == 'hi') {
        fontAssetPath = 'assets/fonts/Hindi.ttf';
      } else if (widget.languageCode == 'kn') {
        fontAssetPath = 'assets/fonts/Kannada.ttf';
      } else {
        fontAssetPath = 'assets/fonts/English.ttf';
      }

      // 2. Load the Font Bytes (rootBundle is now available due to the import)
      final ByteData fontData = await rootBundle.load(fontAssetPath);
      final Uint8List fontBytes = fontData.buffer.asUint8List();

      final Directory appDocDir = await getApplicationDocumentsDirectory();
      // Added logic to ensure filename is safe
      final String safeExerciseName = widget.exerciseName.replaceAll(' ', '');
      final String fileName = 'Workout_Report_${safeExerciseName}_${DateTime.now().millisecondsSinceEpoch}.pdf';
      final String savePath = '${appDocDir.path}/$fileName';

      final List<Map<String, dynamic>> errorReportsData = _errorReports.values
          .map((report) => {
        'error': report.error,
        'imageBytes': report.firstImage,
        'timestamps': report.timestamps,
      }).toList();

      final params = {
        'exerciseName': widget.exerciseName,
        'reps': _currentFeedback.reps,
        'time': _currentFeedback.time,
        'savePath': savePath,
        'errorReports': errorReportsData,
        'fontBytes': fontBytes, // Passing the correct font to the isolate
      };

      final String? resultPath = await compute(_generatePdfInBackground, params);
      return resultPath;
    } catch (e, stackTrace) {
      debugPrint('Error in _generateAndSavePdf: $e');
      return null;
    }
  }
  void _handleEndWorkout() async {
    if (_isSavingReport) return;

    _isWorkoutEnding = true;
    setState(() {
      _isSavingReport = true;
    });

    await _cameraController?.stopImageStream();
    _channel?.sink.close();
    _workoutTimer?.cancel();
    _errorTimer?.cancel();
    await flutterTts.stop();

    if (mounted) {
      showDialog(
        context: context,
        barrierDismissible: false,
        builder: (BuildContext context) => PopScope(
          canPop: false,
          child: AlertDialog(
            backgroundColor: const Color(0xFF1C1C1E),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              children: const [
                CircularProgressIndicator(color: Color(0xFF00C6FF)),
                SizedBox(height: 20),
                Text(
                  'Generating workout report...\nPlease wait',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: Colors.white),
                ),
              ],
            ),
          ),
        ),
      );
    }

    final String? pdfPath = await _generateAndSavePdf();

    if (mounted) {
      Navigator.of(context, rootNavigator: true).pop(); // Close loading
    }

    if (!mounted) return;

    showDialog(
      context: context,
      builder: (BuildContext dialogContext) {
        return AlertDialog(
          backgroundColor: const Color(0xFF1C1C1E),
          title: Text(pdfPath != null ? 'Success!' : 'Error',
              style: TextStyle(color: pdfPath != null ? Colors.green : Colors.red)),
          content: Text(
            pdfPath != null
                ? 'Report saved successfully!\n\nTap OPEN to view.'
                : 'Failed to save report. Please try again.',
            style: const TextStyle(color: Colors.white),
          ),
          actions: [
            if (pdfPath != null)
              TextButton(
                onPressed: () {
                  Navigator.of(dialogContext).pop();
                  Navigator.of(context).popUntil((route) => route.isFirst);
                  OpenFile.open(pdfPath);
                },
                child: const Text('OPEN', style: TextStyle(color: Color(0xFF00C6FF))),
              ),
            TextButton(
              onPressed: () {
                Navigator.of(dialogContext).pop();
                if (pdfPath != null) {
                  Navigator.of(context).popUntil((route) => route.isFirst);
                }
              },
              child: Text(pdfPath != null ? 'CLOSE' : 'OK',
                  style: TextStyle(color: pdfPath != null ? Colors.white70 : const Color(0xFF00C6FF))),
            ),
          ],
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    if (_cameraController == null || !_cameraController!.value.isInitialized) {
      return Scaffold(
        backgroundColor: const Color(0xFF1C1C1E),
        appBar: AppBar(title: Text(widget.exerciseName.toUpperCase())),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    final double screenHeight = MediaQuery.of(context).size.height;
    final double cameraHeight = screenHeight * 0.75;
    final Size cameraPreviewSize = _cameraController!.value.previewSize ?? const Size(1, 1);

    return Scaffold(
      extendBodyBehindAppBar: true,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, color: Colors.white),
          onPressed: () => Navigator.of(context).pop(),
        ),
        title: Text(
          widget.exerciseName.toUpperCase(),
          style: const TextStyle(
            color: Colors.white,
            fontSize: 20,
            fontWeight: FontWeight.bold,
          ),
        ),
        centerTitle: true,
      ),
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            colors: [Color(0xFF1A1A3D), Color(0xFF3A3A6E)],
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
          ),
        ),
        child: Column(
          children: [
            SizedBox(
              height: cameraHeight,
              width: double.infinity,
              child: AspectRatio(
                aspectRatio: cameraPreviewSize.height / cameraPreviewSize.width,
                child: CameraPreview(_cameraController!),
              ),
            ),
            Expanded(
              child: Container(
                width: double.infinity,
                decoration: const BoxDecoration(
                  color: Color(0xFF1C1C1E),
                  borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
                ),
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 15),
                child: Column(
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        _buildInfoColumn('REPS', _currentFeedback.reps.toString().padLeft(2, '0')),
                        _buildInfoColumn('TIME', _currentFeedback.time, crossAxisAlignment: CrossAxisAlignment.end),
                      ],
                    ),
                    const SizedBox(height: 10),
                    Expanded(
                      child: SingleChildScrollView(
                        child: _buildFeedbackChips(),
                      ),
                    ),
                    const SizedBox(height: 10),
                    Center(
                      child: ElevatedButton(
                        onPressed: _isSavingReport ? null : _handleEndWorkout,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.grey.shade800,
                          padding: const EdgeInsets.symmetric(horizontal: 40, vertical: 15),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(30),
                          ),
                        ),
                        child: _isSavingReport
                            ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                            : const Text('END WORKOUT', style: TextStyle(color: Colors.white)),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildInfoColumn(String label, String value, {CrossAxisAlignment crossAxisAlignment = CrossAxisAlignment.start}) {
    return Column(
      crossAxisAlignment: crossAxisAlignment,
      children: [
        Text(
          label,
          style: const TextStyle(
            color: Colors.white70,
            fontSize: 16,
            fontWeight: FontWeight.w500,
          ),
        ),
        Text(
          value,
          style: const TextStyle(
            color: Color(0xFF00C6FF),
            fontSize: 32,
            fontWeight: FontWeight.bold,
          ),
        ),
      ],
    );
  }

  Widget _buildFeedbackChips() {
    if (_stableError.isNotEmpty) {
      return Column(
        children: [
          FeedbackChip(label: 'ERROR: $_stableError', color: Colors.red.shade700),
          const SizedBox(height: 8),
          FeedbackChip(label: 'ADJUST: $_stableError', color: Colors.amber.shade700),
        ],
      );
    }
    if (_currentFeedback.perfectRep) {
      return const FeedbackChip(label: 'PERFECT REP!', color: Color(0xFF00C6FF));
    }
    if (_currentFeedback.adjustment != 'INITIALIZING...') {
      return const FeedbackChip(label: 'GOOD FORM', color: Colors.green);
    }
    // Default/Initial state
    return const FeedbackChip(label: 'INITIALIZING...', color: Colors.grey);
  }
}

class FeedbackChip extends StatelessWidget {
  final String label;
  final Color color;
  const FeedbackChip({super.key, required this.label, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Center(
        child: Text(
          label,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 14,
            fontWeight: FontWeight.w500,
          ),
          overflow: TextOverflow.ellipsis,
          maxLines: 2,
        ),
      ),
    );
  }
}