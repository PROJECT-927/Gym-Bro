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
import 'package:permission_handler/permission_handler.dart';
import 'package:open_file/open_file.dart';
import 'package:frontend/translate.dart';

/// This function runs in a separate isolate (background thread)
/// to avoid freezing the UI.
String _processFrameOnIsolate(Map<String, dynamic> params) {
  final Uint8List bytes = params['bytes'];
  final int width = params['width'];
  final int height = params['height'];
  final int bytesPerRow = params['bytesPerRow'];

  final String base64Image = base64Encode(bytes);
  final Map<String, dynamic> frameData = {
    'frame': base64Image,
    'width': width,
    'height': height,
    'bytesPerRow': bytesPerRow,
  };

  return jsonEncode(frameData);
}

// Placeholder for backend response structure
class Feedback {
  final int reps;
  final String time;
  final String error;
  final String adjustment;
  final bool perfectRep;

  Feedback({
    required this.reps,
    required this.time,
    required this.error,
    required this.adjustment,
    required this.perfectRep,
  });

  factory Feedback.fromJson(Map<String, dynamic> json) {
    return Feedback(
      reps: json['reps'] ?? 0,
      time: json['time'] ?? '00:00',
      error: json['error'] ?? '',
      adjustment: json['adjustment'] ?? '',
      perfectRep: json['perfect_rep'] ?? false,
    );
  }
}

// Class to hold error report data
class ErrorReport {
  final String error;
  final Uint8List firstImage; // The first screenshot (as PNG bytes)
  final List<String> timestamps; // List of all times it occurred

  ErrorReport({
    required this.error,
    required this.firstImage,
    required this.timestamps,
  });
}

class ExerciseWorkoutScreen extends StatefulWidget {
  final String exerciseName;
  final String languageCode;

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

  Feedback _currentFeedback = Feedback(
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
  CameraImage? _currentCameraImage; // Holds the latest camera frame
  bool _isSavingReport = false; // To show loading indicator on button
  bool _isWorkoutEnding =
      false; // FIX: Flag to prevent "Connection Lost" message

  // IMPORTANT: Replace with your computer's local IP address.
  // 1. Make sure your computer and phone are on the SAME Wi-Fi network.
  // 2. Open a command prompt (cmd.exe) on your computer.
  // 3. Type 'ipconfig' and press Enter.
  // 4. Find the 'IPv4 Address' under your Wi-Fi adapter (e.g., 192.168.1.10).
  // 5. Replace the placeholder below with that IP address.
  final String _backendIpAddress = "10.138.56.179"; 
  final int _backendPort = 8765;

  @override
  void initState() {
    super.initState();
    _initializeCamera();
    _connectWebSocket();
    _startWorkoutTimer();
    _initializeTts();
  }

  Future<void> _initializeTts() async {
    await flutterTts.setLanguage(
      AppTranslations.getTtsLocale(widget.languageCode),
    );
    await flutterTts.setSpeechRate(0.5);
    await flutterTts.setVolume(1.0);
    await flutterTts.setPitch(1.0);
  }

  Future<void> _speak(String text) async {
    await flutterTts.speak(text);
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
        ResolutionPreset.medium,
        enableAudio: false,
        imageFormatGroup: ImageFormatGroup.yuv420,
      );

      try {
        await _cameraController!.initialize();
        if (mounted) {
          setState(() {});
        }
        _startImageStream();
      } on CameraException catch (e) {
        debugPrint("Camera Error: $e");
      }
    } else {
      debugPrint("No cameras available.");
    }
  }

  void _startImageStream() {
    _cameraController?.startImageStream((CameraImage image) async {
      // Capture latest frame for screenshot purposes
      _currentCameraImage = image;

      if (_channel == null || _isProcessingFrame) {
        return;
      }
      _isProcessingFrame = true;

      try {
        final Map<String, dynamic> isolateParams = {
          'bytes': Uint8List.fromList(image.planes[0].bytes),
          'width': image.width,
          'height': image.height,
          'bytesPerRow': image.planes[0].bytesPerRow,
        };

        final String jsonString = await compute(
          _processFrameOnIsolate,
          isolateParams,
        );

        if (mounted) {
          _channel!.sink.add(jsonString);
        }
      } catch (e) {
        debugPrint("Error sending frame: $e");
      } finally {
        await Future.delayed(const Duration(milliseconds: 100));
        _isProcessingFrame = false;
      }
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
            final Map<String, dynamic> data = jsonDecode(message);
            // final Feedback newFeedback = Feedback.fromJson(
            //   data,
            // ).copyWithTime(_currentFeedback.time);
            String rawError = data['error'] ?? '';
            String rawAdjustment = data['adjustment'] ?? '';

            // Use widget.languageCode here
            String displayError = AppTranslations.translate(
              rawError,
              widget.languageCode,
            );
            String displayAdjustment = AppTranslations.translate(
              rawAdjustment,
              widget.languageCode,
            );

            // Update Feedback object with TRANSLATED text
            final Feedback newFeedback = Feedback(
              reps: data['reps'] ?? 0,
              time: _currentFeedback.time,
              error: displayError,
              adjustment: displayAdjustment,
              perfectRep: data['perfect_rep'] ?? false,
            );

            final String newError = newFeedback.error;
            final String currentTime = newFeedback.time;

            // Error logging logic
            if (newError.isNotEmpty && _currentCameraImage != null) {
              if (!_errorReports.containsKey(newError)) {
                // First time seeing this error. Take snapshot.
                _captureErrorScreenshot(
                  newError,
                  currentTime,
                  _currentCameraImage!,
                );
              } else {
                // Subsequent time. Just add timestamp if it's different.
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
          }
        },
        onDone: () {
          debugPrint('WebSocket connection closed!');
          _errorTimer?.cancel();
          // FIX: Don't show "CONNECTION LOST" if we are ending the workout intentionally.
          if (_isWorkoutEnding) return;
          if (mounted) {
            setState(() {
              _stableError = 'CONNECTION LOST';
            });
            _speak("Connection Lost");
          }
        },
        onError: (error) {
          debugPrint('WebSocket error: $error');
          _errorTimer?.cancel();
          if (mounted) {
            setState(() {
              _stableError = 'CONNECTION ERROR';
            });
            _speak("Connection Error");
          }
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

  // Helper to capture and convert screenshot
  void _captureErrorScreenshot(
    String error,
    String time,
    CameraImage cameraImage,
  ) async {
    try {
      // This conversion runs in the background
      final Uint8List? pngBytes = await compute(_convertYUVtoPNG, cameraImage);

      if (pngBytes != null && mounted) {
        setState(() {
          _errorReports[error] = ErrorReport(
            error: error,
            firstImage: pngBytes,
            timestamps: [time],
          );
        });
        debugPrint("Screenshot captured for error: $error");
      } else {
        debugPrint("Failed to convert image for error: $error");
      }
    } catch (e) {
      debugPrint("Error capturing screenshot: $e");
    }
  }

  // Helper function to convert CameraImage to PNG
  // This MUST be a top-level function or a static method to be used with compute
  static Uint8List? _convertYUVtoPNG(CameraImage image) {
    try {
      final int width = image.width;
      final int height = image.height;
      final int uvRowStride = image.planes[1].bytesPerRow;
      final int? uvPixelStride = image.planes[1].bytesPerPixel;

      final yPlane = image.planes[0].bytes;
      final uPlane = image.planes[1].bytes;
      final vPlane = image.planes[2].bytes;

      var convertedImage = img.Image(width: width, height: height);
      for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
          final int uvIndex =
              uvPixelStride! * (x / 2).floor() + uvRowStride * (y / 2).floor();
          final int index = y * width + x;

          final yp = yPlane[index];
          final up = uPlane[uvIndex];
          final vp = vPlane[uvIndex];

          int r = (yp + 1.402 * (vp - 128)).round();
          int g = (yp - 0.344136 * (up - 128) - 0.714136 * (vp - 128)).round();
          int b = (yp + 1.772 * (up - 128)).round();

          convertedImage.setPixelRgba(
            x,
            y,
            r.clamp(0, 255),
            g.clamp(0, 255),
            b.clamp(0, 255),
            255,
          );
        }
      }

      // Rotate the image because camera output is often landscape
      // Adjust rotation angle if needed for your setup
      final img.Image rotatedImage = img.copyRotate(convertedImage, angle: 90);
      return Uint8List.fromList(img.encodePng(rotatedImage));
    } catch (e) {
      debugPrint("Error converting image: $e");
      return null;
    }
  }

  void _startWorkoutTimer() {
    _workoutTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (mounted) {
        setState(() {
          _timeInSeconds++;
          int minutes = _timeInSeconds ~/ 60;
          int seconds = _timeInSeconds % 60;
          _currentFeedback = _currentFeedback.copyWith(
            time:
                '${minutes.toString().padLeft(2, '0')}:${seconds.toString().padLeft(2, '0')}',
          );
        });
      }
    });
  }

  // NEW: Background PDF generation function
  static Future<String?> _generatePdfInBackground(
    Map<String, dynamic> params,
  ) async {
    try {
      final String exerciseName = params['exerciseName'];
      final int reps = params['reps'];
      final String time = params['time'];
      final String savePath = params['savePath'];
      final List<Map<String, dynamic>> errorReportsData =
          params['errorReports'];

      final pdf = pw.Document();
      final String dateTime = DateTime.now().toLocal().toString().split('.')[0];

      // Title Page
      pdf.addPage(
        pw.Page(
          build: (pw.Context context) {
            return pw.Center(
              child: pw.Column(
                mainAxisAlignment: pw.MainAxisAlignment.center,
                children: [
                  pw.Text(
                    'Workout Report',
                    style: pw.TextStyle(
                      fontSize: 40,
                      fontWeight: pw.FontWeight.bold,
                    ),
                  ),
                  pw.SizedBox(height: 20),
                  pw.Text(
                    exerciseName.toUpperCase(),
                    style: const pw.TextStyle(fontSize: 24),
                  ),
                  pw.SizedBox(height: 10),
                  pw.Text(dateTime, style: const pw.TextStyle(fontSize: 18)),
                  pw.SizedBox(height: 30),
                  pw.Text(
                    'Total Reps: $reps',
                    style: const pw.TextStyle(fontSize: 20),
                  ),
                  pw.Text(
                    'Total Time: $time',
                    style: const pw.TextStyle(fontSize: 20),
                  ),
                  pw.SizedBox(height: 50),
                  pw.Text(
                    errorReportsData.isEmpty
                        ? 'No errors detected. Great job!'
                        : 'Found ${errorReportsData.length} unique error(s).',
                    style: pw.TextStyle(
                      fontSize: 18,
                      color: errorReportsData.isEmpty
                          ? PdfColors.green
                          : PdfColors.red,
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
        final List<String> timestamps = List<String>.from(
          reportData['timestamps'],
        );

        final pdfImage = pw.MemoryImage(imageBytes);

        pdf.addPage(
          pw.Page(
            build: (pw.Context context) {
              return pw.Column(
                crossAxisAlignment: pw.CrossAxisAlignment.start,
                children: [
                  pw.Text(
                    'ERROR: $error',
                    style: pw.TextStyle(
                      fontSize: 24,
                      fontWeight: pw.FontWeight.bold,
                      color: PdfColors.red,
                    ),
                  ),
                  pw.SizedBox(height: 20),
                  pw.Center(
                    child: pw.Container(
                      height: 400,
                      child: pw.Image(pdfImage, fit: pw.BoxFit.contain),
                    ),
                  ),
                  pw.SizedBox(height: 20),
                  pw.Text(
                    'Occurred at:',
                    style: pw.TextStyle(
                      fontSize: 18,
                      fontWeight: pw.FontWeight.bold,
                    ),
                  ),
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

      // Save file
      final File file = File(savePath);
      await file.writeAsBytes(await pdf.save());

      debugPrint('Report saved to $savePath');
      return savePath;
    } catch (e) {
      debugPrint('Error generating PDF in background: $e');
      return null;
    }
  }

  // REVISED: Function to generate and save the PDF
  Future<String?> _generateAndSavePdf() async {
    try {
      debugPrint("Starting PDF generation...");

      // 1. Get a directory where we can save the file.
      // getApplicationDocumentsDirectory is private to the app and requires no permissions.
      final Directory appDocDir = await getApplicationDocumentsDirectory();
      final String fileName =
          'Workout_Report_${widget.exerciseName.replaceAll(' ', '_')}_${DateTime.now().millisecondsSinceEpoch}.pdf';
      final String savePath = '${appDocDir.path}/$fileName';

      debugPrint("Final save path: $savePath");

      // 2. Prepare error reports data for background processing
      final List<Map<String, dynamic>> errorReportsData = _errorReports.values
          .map((report) {
            return {
              'error': report.error,
              'imageBytes': report.firstImage,
              'timestamps': report.timestamps,
            };
          })
          .toList();

      debugPrint("Prepared ${errorReportsData.length} error reports");

      // 3. Generate PDF in background isolate
      final Map<String, dynamic> params = {
        'exerciseName': widget.exerciseName,
        'reps': _currentFeedback.reps,
        'time': _currentFeedback.time,
        'savePath': savePath,
        'errorReports': errorReportsData,
      };

      debugPrint("Starting background PDF generation...");
      final String? resultPath = await compute(
        _generatePdfInBackground,
        params,
      );

      if (resultPath != null) {
        debugPrint("PDF generation completed successfully: $resultPath");
      } else {
        debugPrint("PDF generation failed");
      }

      return resultPath;
    } catch (e, stackTrace) {
      debugPrint('Error in _generateAndSavePdf: $e');
      debugPrint('Stack trace: $stackTrace');
      return null;
    }
  }

  // REVISED: Function to handle ending the workout
  void _handleEndWorkout() async {
    if (_isSavingReport) return;

    // Set flags to manage state
    _isWorkoutEnding = true;
    setState(() {
      _isSavingReport = true;
    });

    // Stop all activities
    await _cameraController?.stopImageStream();
    _channel?.sink.close();
    _workoutTimer?.cancel();
    _errorTimer?.cancel();
    await flutterTts.stop();

    // Show "Generating report..." dialog
    if (mounted) {
      showDialog(
        context: context,
        barrierDismissible: false,
        builder: (BuildContext context) {
          return PopScope(
            canPop: false, // Prevent dismissing
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
          );
        },
      );
    }

    // Generate PDF in background
    final String? pdfPath = await _generateAndSavePdf();

    // Close "Generating report..." dialog
    if (mounted) {
      Navigator.of(context, rootNavigator: true).pop();
    }

    if (!mounted) return;

    // Show final result dialog (Success or Failure)
    if (pdfPath != null) {
      showDialog(
        context: context,
        builder: (BuildContext dialogContext) {
          return AlertDialog(
            backgroundColor: const Color(0xFF1C1C1E),
            title: const Text(
              'Success!',
              style: TextStyle(color: Colors.green),
            ),
            content: const Text(
              'Report saved successfully!\n\nTap OPEN to view.',
              style: TextStyle(color: Colors.white),
            ),
            actions: [
              TextButton(
                onPressed: () {
                  Navigator.of(dialogContext).pop();
                  Navigator.of(context).popUntil((route) => route.isFirst);
                  OpenFile.open(pdfPath);
                },
                child: const Text(
                  'OPEN',
                  style: TextStyle(color: Color(0xFF00C6FF)),
                ),
              ),
              TextButton(
                onPressed: () {
                  Navigator.of(dialogContext).pop();
                  Navigator.of(context).popUntil((route) => route.isFirst);
                },
                child: const Text(
                  'CLOSE',
                  style: TextStyle(color: Colors.white70),
                ),
              ),
            ],
          );
        },
      );
    } else {
      showDialog(
        context: context,
        builder: (BuildContext dialogContext) {
          return AlertDialog(
            backgroundColor: const Color(0xFF1C1C1E),
            title: const Text('Error', style: TextStyle(color: Colors.red)),
            content: const Text(
              'Failed to save report. Please try again.',
              style: TextStyle(color: Colors.white),
            ),
            actions: [
              TextButton(
                onPressed: () {
                  Navigator.of(dialogContext).pop();
                  Navigator.of(context).popUntil((route) => route.isFirst);
                },
                child: const Text(
                  'OK',
                  style: TextStyle(color: Color(0xFF00C6FF)),
                ),
              ),
            ],
          );
        },
      );
    }
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
    final Size cameraPreviewSize = _cameraController!.value.previewSize!;

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
            // Camera Preview
            SizedBox(
              height: cameraHeight,
              width: double.infinity,
              child: AspectRatio(
                aspectRatio: cameraPreviewSize.height / cameraPreviewSize.width,
                child: CameraPreview(_cameraController!),
              ),
            ),
            // Feedback Section
            Expanded(
              child: Container(
                width: double.infinity,
                decoration: const BoxDecoration(
                  color: Color(0xFF1C1C1E),
                  borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
                ),
                padding: const EdgeInsets.symmetric(
                  horizontal: 20,
                  vertical: 15,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Reps and Time Row
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'REPS:',
                              style: TextStyle(
                                color: Colors.white70,
                                fontSize: 16,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                            Text(
                              _currentFeedback.reps.toString().padLeft(2, '0'),
                              style: const TextStyle(
                                color: Color(0xFF00C6FF),
                                fontSize: 32,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        ),
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: [
                            const Text(
                              'TIME:',
                              style: TextStyle(
                                color: Colors.white70,
                                fontSize: 16,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                            Text(
                              _currentFeedback.time,
                              style: const TextStyle(
                                color: Color(0xFF00C6FF),
                                fontSize: 32,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                    const SizedBox(height: 10),

                    // Scrollable Feedback Area
                    Expanded(
                      child: SingleChildScrollView(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            if (_stableError.isNotEmpty &&
                                !_currentFeedback.perfectRep) ...[
                              FeedbackChip(
                                label: 'ERROR: $_stableError',
                                color: Colors.red.shade700,
                              ),
                              const SizedBox(height: 8),
                              FeedbackChip(
                                label: 'ADJUST: $_stableError',
                                color: Colors.amber.shade700,
                              ),
                            ] else if (_stableError.isEmpty &&
                                !_currentFeedback.perfectRep &&
                                _currentFeedback.adjustment !=
                                    'INITIALIZING...')
                              const FeedbackChip(
                                label: 'GOOD FORM',
                                color: Colors.green,
                              ),
                            if (_currentFeedback.perfectRep &&
                                _stableError.isEmpty)
                              const FeedbackChip(
                                label: 'PERFECT REP!',
                                color: Color(0xFF00C6FF),
                              ),
                          ],
                        ),
                      ),
                    ),

                    const SizedBox(height: 10),
                    // End Workout Button
                    Center(
                      child: ElevatedButton(
                        onPressed: _isSavingReport ? null : _handleEndWorkout,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.grey.shade800,
                          padding: const EdgeInsets.symmetric(
                            horizontal: 40,
                            vertical: 15,
                          ),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(30),
                          ),
                          textStyle: const TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
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
                            : const Text(
                                'END WORKOUT',
                                style: TextStyle(color: Colors.white),
                              ),
                      ),
                    ),
                    const SizedBox(height: 5),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// UI Widget for displaying error/status tags
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
    );
  }
}

// Extensions to help copy Feedback objects with new values
extension on Feedback {
  Feedback copyWith({
    int? reps,
    String? time,
    String? error,
    String? adjustment,
    bool? perfectRep,
  }) {
    return Feedback(
      reps: reps ?? this.reps,
      time: time ?? this.time,
      error: error ?? this.error,
      adjustment: adjustment ?? this.adjustment,
      perfectRep: perfectRep ?? this.perfectRep,
    );
  }

  Feedback copyWithTime(String newTime) {
    return Feedback(
      reps: reps,
      time: newTime,
      error: error,
      adjustment: adjustment,
      perfectRep: perfectRep,
    );
  }
}
