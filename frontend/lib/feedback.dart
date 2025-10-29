import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'dart:isolate';
import 'dart:typed_data'; // We need this for Uint8List
import 'dart:async';
import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/io.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_tts/flutter_tts.dart'; // <-- 1. IMPORT TTS

/// This function runs in a separate isolate (background thread)
/// to avoid freezing the UI.
String _processFrameOnIsolate(Map<String, dynamic> params) {
  // 1. Get the data from the main thread
  final Uint8List bytes = params['bytes'];
  final int width = params['width'];
  final int height = params['height'];
  final int bytesPerRow = params['bytesPerRow'];

  // 2. Do all the heavy work here
  final String base64Image = base64Encode(bytes);
  final Map<String, dynamic> frameData = {
    'frame': base64Image,
    'width': width,
    'height': height,
    'bytesPerRow': bytesPerRow,
  };

  // 3. Return the final JSON string
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
      time: json['time'] ?? '00:00', // Backend might send this, or client tracks it
      error: json['error'] ?? '',
      adjustment: json['adjustment'] ?? '',
      perfectRep: json['perfect_rep'] ?? false,
    );
  }
}

class ExerciseWorkoutScreen extends StatefulWidget {
  final String exerciseName;
  const ExerciseWorkoutScreen({super.key, required this.exerciseName});

  @override
  State<ExerciseWorkoutScreen> createState() => _ExerciseWorkoutScreenState();
}

class _ExerciseWorkoutScreenState extends State<ExerciseWorkoutScreen> {
  CameraController? _cameraController;
  WebSocketChannel? _channel;
  FlutterTts flutterTts = FlutterTts(); // <-- 2. TTS Instance

  Feedback _currentFeedback = Feedback(
    reps: 0,
    time: '00:00',
    // error: 'NO ERRORS DETECTED', // Start with no error shown
    error: '', // Start with no error shown
    adjustment: 'INITIALIZING...',
    perfectRep: false,
  );
  Timer? _workoutTimer;
  int _timeInSeconds = 0;
  bool _isProcessingFrame = false; // To prevent sending too many frames too quickly

  // --- 3. State variables for 2-second "Wait" logic ---
  Timer? _errorTimer;
  String _potentialError = ""; // Error received from backend
  String _stableError = "";    // Error displayed/spoken after 2s
  String _lastSpokenError = ""; // To prevent re-speaking the same stable error

  // --- IMPORTANT ---
  // Replace with your computer's local IP address and the port used by the Python server
  final String _backendIpAddress = "10.81.135.95"; // E.g., "192.168.1.100"
  final int _backendPort = 8765;
  // ---------------

  @override
  void initState() {
    super.initState();
    _initializeCamera();
    _connectWebSocket();
    _startWorkoutTimer();
    _initializeTts(); // <-- 4. Initialize TTS
  }

  // --- 5. Initialize TTS ---
  Future<void> _initializeTts() async {
    await flutterTts.setLanguage("en-US");
    await flutterTts.setSpeechRate(0.5); // Adjust rate as needed
    await flutterTts.setVolume(1.0);
    await flutterTts.setPitch(1.0);
  }

  // --- 6. Speak function ---
  Future<void> _speak(String text) async {
    await flutterTts.speak(text);
  }


  Future<void> _initializeCamera() async {
    final cameras = await availableCameras();
    if (cameras.isNotEmpty) {

      CameraDescription frontCamera;
      try {
        frontCamera = cameras.firstWhere(
            (camera) => camera.lensDirection == CameraLensDirection.front);
      } catch (e) {
        debugPrint("No front camera found, using first available camera.");
        frontCamera = cameras[0];
      }

      _cameraController = CameraController(
        frontCamera, // Use the selected front camera
        ResolutionPreset.medium,
        enableAudio: false,
      );

      try {
        await _cameraController!.initialize();
        if (mounted) {
          setState(() {}); // Update UI after camera init
        }
        _startImageStream(); // Start sending frames
      } on CameraException catch (e) {
        debugPrint("Camera Error: $e");
        // Handle error, e.g., show a message to the user
      }
    } else {
      debugPrint("No cameras available.");
      // Handle no camera availability
    }
  }

  void _startImageStream() {
    _cameraController?.startImageStream((CameraImage image) async {
      if (_channel == null || _isProcessingFrame) {
        return;
      }
      _isProcessingFrame = true; // Set flag to true

      try {

        // 1. Prepare data for the isolate.
        final Map<String, dynamic> isolateParams = {
          'bytes': Uint8List.fromList(image.planes[0].bytes), // <-- IMPORTANT: Make a copy
          'width': image.width,
          'height': image.height,
          'bytesPerRow': image.planes[0].bytesPerRow,
        };

        // 2. Run the heavy encoding on a separate thread (isolate).
        final String jsonString =
            await compute(_processFrameOnIsolate, isolateParams);

        // 3. Send the result (which is now just a string).
        if (mounted) { // Check if the widget is still in the tree
          _channel!.sink.add(jsonString);
        }

      } catch (e) {
        debugPrint("Error sending frame: $e");
      } finally {
        // Delay to control the frame rate
        await Future.delayed(const Duration(milliseconds: 100)); // ~10 FPS
        _isProcessingFrame = false; // Reset flag
      }
    });
  }


  void _connectWebSocket() {
    try {
      final uri = Uri.parse('ws://$_backendIpAddress:$_backendPort');
      _channel = IOWebSocketChannel.connect(uri);
      debugPrint("Attempting to connect to WebSocket: $uri");

      // --- 7. UPDATED 2-SECOND "WAIT" LOGIC FOR TTS ---
      _channel!.stream.listen(
        (message) {
          if (mounted) {
            final Map<String, dynamic> data = jsonDecode(message);
            final Feedback newFeedback =
                Feedback.fromJson(data).copyWithTime(_currentFeedback.time);

            // Raw error from Python (should be single string now)
            final String newError = newFeedback.error;

            // --- 1. Update Reps/Time Immediately ---
            // Keep the currently displayed _stableError for now
            setState(() {
              _currentFeedback = newFeedback.copyWith(error: _stableError);
            });

             // Removed Error Frequency Tracking

            // --- 2. 2-Second "Wait" Logic ---
            if (newError != _potentialError) {
              // Error changed (or went away). Reset timer and track new one.
              _errorTimer?.cancel();
              _potentialError = newError;

              if (newError.isEmpty) {
                // Good form received. Clear stable error immediately.
                setState(() { _stableError = ""; });
                _lastSpokenError = ""; // Ready to speak next error
              } else {
                // New potential error. Start the 2-second timer.
                _errorTimer = Timer(const Duration(seconds: 2), () {
                  // --- TIMER FIRED! ---
                  // Check if the error is *still* the one we were tracking.
                  if (mounted && _potentialError == newError) {
                    // Yes, persisted for 2s. Make it stable.
                    setState(() { _stableError = newError; });

                    // Speak it, ONLY if it's different from the last *stable* error spoken.
                    if (_stableError != _lastSpokenError) {
                      _speak(_stableError);
                      _lastSpokenError = _stableError; // Remember what we just spoke
                    }
                  }
                });
              }
            }
            // else: Error is the same as potential error, timer is running or fired. Do nothing.
          }
        },
        onDone: () {
          debugPrint('WebSocket connection closed!');
          _errorTimer?.cancel();
          if (mounted) {
            setState(() { _stableError = 'CONNECTION LOST'; });
            _speak("Connection Lost");
            // Removed handleWorkoutEnd call
          }
        },
        onError: (error) {
          debugPrint('WebSocket error: $error');
          _errorTimer?.cancel();
          if (mounted) {
            setState(() { _stableError = 'CONNECTION ERROR'; });
            _speak("Connection Error");
            // Removed handleWorkoutEnd call
          }
        },
      );
    } catch (e) {
      debugPrint("WebSocket connection failed to establish: $e");
      if (mounted) {
        setState(() { _stableError = 'WS INIT FAILED'; });
         // Removed handleWorkoutEnd call
      }
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

  // Removed _handleWorkoutEnd function
  // Removed _generateAndSavePdf function

  @override
  void dispose() {
    // Removed handleWorkoutEnd call

    _cameraController?.stopImageStream();
    _cameraController?.dispose();
    _channel?.sink.close();
    _workoutTimer?.cancel();
    _errorTimer?.cancel(); // <-- 8. Cancel error timer
    flutterTts.stop();     // <-- 9. Stop TTS
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
    final double cameraHeight = screenHeight * 0.75; // 75% for camera
    final Size cameraPreviewSize = _cameraController!.value.previewSize!;

    return Scaffold(
      extendBodyBehindAppBar: true,
      appBar: AppBar(
         backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, color: Colors.white),
          onPressed: () => Navigator.of(context).pop(), // Just pop now
        ),
        title: Text(
          widget.exerciseName.toUpperCase(),
           style: const TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold),
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
            Expanded( // Use Expanded to take remaining space
              child: Container(
                width: double.infinity, // Ensure it takes full width
                decoration: const BoxDecoration(
                  color: Color(0xFF1C1C1E),
                  borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
                ),
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 15),
                child: Column( // Main column for feedback section
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                     // Reps and Time Row
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        // Reps Column
                         Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text('REPS:', style: TextStyle(color: Colors.white70, fontSize: 16, fontWeight: FontWeight.w500)),
                            Text(_currentFeedback.reps.toString().padLeft(2, '0'), style: const TextStyle(color: Color(0xFF00C6FF), fontSize: 32, fontWeight: FontWeight.bold)),
                          ],
                        ),
                        // Time Column
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: [
                             const Text('TIME:', style: TextStyle(color: Colors.white70, fontSize: 16, fontWeight: FontWeight.w500)),
                             Text(_currentFeedback.time, style: const TextStyle(color: Color(0xFF00C6FF), fontSize: 32, fontWeight: FontWeight.bold)),
                          ],
                        ),
                      ],
                    ),
                    const SizedBox(height: 10), // Reduced spacing

                    // --- SCROLLABLE FEEDBACK AREA ---
                    Expanded( // Make this area take available vertical space
                      child: SingleChildScrollView( // Make chips scrollable
                        child: Column(
                           crossAxisAlignment: CrossAxisAlignment.start,
                           children: [
                              // --- 10. Display _stableError ---
                              if (_stableError.isNotEmpty && !_currentFeedback.perfectRep) ...[
                                FeedbackChip(label: 'ERROR: $_stableError', color: Colors.red.shade700),
                                const SizedBox(height: 8),
                                FeedbackChip(label: 'ADJUST: $_stableError', color: Colors.amber.shade700),
                              ]
                              // --- Good Form Chip ---
                              else if (_stableError.isEmpty && !_currentFeedback.perfectRep && _currentFeedback.adjustment != 'INITIALIZING...')
                                const FeedbackChip(label: 'GOOD FORM', color: Colors.green),

                              // --- Perfect Rep Chip ---
                              if (_currentFeedback.perfectRep && _stableError.isEmpty)
                                const FeedbackChip(label: 'PERFECT REP!', color: Color(0xFF00C6FF)),
                           ]
                        ),
                      ),
                    ),
                     // --- END SCROLLABLE AREA ---

                    const SizedBox(height: 10), // Spacing before button
                    // End Workout Button (ensure it's at the bottom)
                    Center(
                      child: ElevatedButton(
                        onPressed: () {
                           Navigator.of(context).pop(); // Just pop now
                           ScaffoldMessenger.of(context).showSnackBar(
                             const SnackBar(content: Text('Workout ended!')),
                           );
                        },
                         style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.grey.shade800,
                          padding: const EdgeInsets.symmetric(horizontal: 40, vertical: 15),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(30)),
                          textStyle: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                        ),
                        child: const Text('END WORKOUT', style: TextStyle(color: Colors.white)),
                      ),
                    ),
                    const SizedBox(height: 5), // Small padding at bottom
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

// FeedbackChip widget remains the same
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
        style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w500,),
        overflow: TextOverflow.ellipsis, // Prevent text overflow visually
        maxLines: 2, // Allow up to 2 lines if needed
      ),
    );
  }
}


// Feedback extensions remain the same
extension on Feedback {
  Feedback copyWith({
    int? reps, String? time, String? error, String? adjustment, bool? perfectRep,
  }) {
    return Feedback(
      reps: reps ?? this.reps, time: time ?? this.time, error: error ?? this.error,
      adjustment: adjustment ?? this.adjustment, perfectRep: perfectRep ?? this.perfectRep,
    );
  }
  Feedback copyWithTime(String newTime) {
    return Feedback(
      reps: reps, time: newTime, error: error, adjustment: adjustment, perfectRep: perfectRep,
    );
  }
}

