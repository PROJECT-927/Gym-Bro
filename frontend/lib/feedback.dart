import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'dart:isolate';
import 'dart:typed_data'; // We need this for Uint8List
import 'dart:async';
import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/io.dart'; 
import 'package:flutter/foundation.dart';

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
  Feedback _currentFeedback = Feedback(
    reps: 0,
    time: '00:00',
    error: 'NO ERRORS DETECTED',
    adjustment: 'INITIALIZING...',
    perfectRep: false,
  );
  Timer? _workoutTimer;
  int _timeInSeconds = 0;
  bool _isProcessingFrame = false; // To prevent sending too many frames too quickly

  // --- IMPORTANT ---
  // Replace with your computer's local IP address and the port used by the Python server
  final String _backendIpAddress = "10.61.76.179"; // E.g., "192.168.1.100"
  final int _backendPort = 8765;
  // ---------------

  @override
  void initState() {
    super.initState();
    _initializeCamera();
    _connectWebSocket();
    _startWorkoutTimer();
  }

  Future<void> _initializeCamera() async {
    final cameras = await availableCameras();
    if (cameras.isNotEmpty) {

      // _cameraController = CameraController(
      //   cameras[0], // Use the first camera (usually back)
      //   ResolutionPreset.medium,
      //   enableAudio: false,
      // );

      // Find the front camera
      CameraDescription frontCamera;
      try {
        frontCamera = cameras.firstWhere(
          (camera) => camera.lensDirection == CameraLensDirection.front
        );
      } catch (e) {
        // If no front camera is found, default to the first camera
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
        // --- THIS IS THE KEY CHANGE ---
        
        // 1. Prepare data for the isolate.
        // We MUST copy the bytes, as the original image buffer will be
        // reused by the camera.
        final Map<String, dynamic> isolateParams = {
          'bytes': Uint8List.fromList(image.planes[0].bytes), // <-- IMPORTANT: Make a copy
          'width': image.width,
          'height': image.height,
          'bytesPerRow': image.planes[0].bytesPerRow,
        };

        // 2. Run the heavy encoding on a separate thread (isolate). 
        // This 'await' waits for the background thread to finish.
        final String jsonString = await compute(_processFrameOnIsolate, isolateParams);

        // 3. Send the result (which is now just a string). This is very fast.
        if (mounted) { // Check if the widget is still in the tree
          _channel!.sink.add(jsonString);
        }
        // --- END OF KEY CHANGE ---

      } catch (e) {
        debugPrint("Error sending frame: $e");
      } finally {
        // We still need this delay to control the frame rate to the server
        await Future.delayed(const Duration(milliseconds: 100)); // 10 FPS
        _isProcessingFrame = false; // Reset flag
      }
    });
  }


  void _connectWebSocket() {
    try {
      final uri = Uri.parse('ws://$_backendIpAddress:$_backendPort');
      _channel = IOWebSocketChannel.connect(uri);
      debugPrint("Attempting to connect to WebSocket: $uri");

      _channel!.stream.listen(
        (message) {
          debugPrint("Received from backend: $message");
          if (mounted) {
            setState(() {
              final Map<String, dynamic> data = jsonDecode(message);
              // Backend is sending reps, error, adjustment, perfect_rep
              // We'll update our local _timeInSeconds based time separately
              _currentFeedback = Feedback.fromJson(data).copyWithTime(_currentFeedback.time);
            });
          }
        },
        onDone: () {
          debugPrint('WebSocket connection closed!');
          if (mounted) {
            setState(() {
              _currentFeedback = _currentFeedback.copyWith(
                  error: 'CONNECTION LOST', adjustment: 'Please restart workout.');
            });
            // Optionally try to reconnect
            // Future.delayed(const Duration(seconds: 5), _connectWebSocket);
          }
        },
        onError: (error) {
          debugPrint('WebSocket error: $error');
          if (mounted) {
            setState(() {
              _currentFeedback = _currentFeedback.copyWith(
                  error: 'CONNECTION ERROR', adjustment: 'Check server & network.');
            });
            // Optionally try to reconnect
            // Future.delayed(const Duration(seconds: 5), _connectWebSocket);
          }
        },
      );
    } catch (e) {
      debugPrint("WebSocket connection failed to establish: $e");
      if (mounted) {
        setState(() {
          _currentFeedback = _currentFeedback.copyWith(
              error: 'WS INIT FAILED', adjustment: 'Is server running?');
        });
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
            time: '${minutes.toString().padLeft(2, '0')}:${seconds.toString().padLeft(2, '0')}',
          );
        });
      }
    });
  }

  @override
  void dispose() {
    _cameraController?.stopImageStream();
    _cameraController?.dispose();
    _channel?.sink.close();
    _workoutTimer?.cancel();
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
            // Camera Preview (approx. 75% of screen height)
            SizedBox(
              height: cameraHeight,
              width: double.infinity,
              child: AspectRatio(
                aspectRatio: cameraPreviewSize.height / cameraPreviewSize.width, // Adjusted for full width
                child: CameraPreview(_cameraController!),
              ),
            ),
            // Feedback Section (Remaining 25% of screen height)
            Expanded(
              child: Container(
                decoration: const BoxDecoration(
                  color: Color(0xFF1C1C1E),
                  borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
                ),
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 15),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
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
                    const SizedBox(height: 20),
                    // Error Message
                    if (_currentFeedback.error.isNotEmpty && !_currentFeedback.perfectRep)
                      FeedbackChip(
                        label: 'ERROR: ${_currentFeedback.error}',
                        color: Colors.red.shade700,
                      ),
                    const SizedBox(height: 8),
                    // Adjustment Message
                    if (_currentFeedback.adjustment.isNotEmpty && !_currentFeedback.perfectRep)
                      FeedbackChip(
                        label: 'ADJUST: ${_currentFeedback.adjustment}',
                        color: Colors.amber.shade700,
                      ),
                    if (_currentFeedback.perfectRep)
                      const FeedbackChip(
                        label: 'PERFECT REP!',
                        color: Color(0xFF00C6FF),
                      ),
                    const Spacer(),
                    // End Workout Button
                    Center(
                      child: ElevatedButton(
                        onPressed: () {
                          Navigator.of(context).pop();
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('Workout ended!')),
                          );
                        },
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.grey.shade800,
                          padding: const EdgeInsets.symmetric(horizontal: 40, vertical: 15),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(30),
                          ),
                          textStyle: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                        ),
                        child: const Text('END WORKOUT', style: TextStyle(color: Colors.white)),
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
}

// Reusable widget for displaying feedback chips (unchanged)
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
      ),
    );
  }
}

// Extension to allow copying BackendFeedback with updated fields
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

  // Specifically for updating time from local timer
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