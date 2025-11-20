import 'package:flutter/material.dart';
import 'feedback.dart';
import 'package:shared_preferences/shared_preferences.dart';
import  'ProfilePage.dart';

class Exercise {
  final String name;
  final String imagePath;

  Exercise({required this.name, required this.imagePath});
}

// --- Main Menu Screen Widget ---
class ExerciseMenuScreen extends StatefulWidget {
  const ExerciseMenuScreen({super.key});

  @override
  State<ExerciseMenuScreen> createState() => _ExerciseMenuScreenState();
}

class _ExerciseMenuScreenState extends State<ExerciseMenuScreen> {
  // List of exercises
  final List<Exercise> exercises = [
    Exercise(name: 'SHOULDER PRESS', imagePath: 'assets/shoulder_press.jpg'),
    Exercise(name: 'BARBELL CURLS', imagePath: 'assets/barbell_curls.webp'),
    Exercise(name: 'PLANK', imagePath: 'assets/shoulder_press.jpg'),
    Exercise(name: 'SQUATS', imagePath: 'assets/squats.jpg'),
    Exercise(name: 'PUSHUPS', imagePath: 'assets/squats.jpg'),
  ];

  String? _selectedExercise; // To track the currently selected exercise

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      extendBodyBehindAppBar: true, // Keeps gradient behind the header
  appBar: AppBar(
    backgroundColor: Colors.transparent, // Invisible background
    elevation: 0, // No shadow
    // 'actions' are always on the RIGHT side
    actions: [
      IconButton(
        icon: const Icon(Icons.person, color: Colors.white, size: 30),
        onPressed: () {
          Navigator.push(
            context,
            MaterialPageRoute(builder: (context) => const ProfilePage()),
          );
        },
      ),
      const SizedBox(width: 15), // Padding from the right edge
    ],
  ),
      body: Container(
        // Background Gradient
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            colors: [Color(0xFF1A1A3D), Color(0xFF3A3A6E)],
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
          ),
        ),
        child: SafeArea(
          child: Column(
            children: [
              // Header Title
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 40.0),
                child: Column(
                  children: [
                    Text(
                      'GYM POSTURE ANALYZER',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 24,
                        fontWeight: FontWeight.bold,
                        letterSpacing: 1.5,
                      ),
                    ),
                    SizedBox(height: 8),
                    Text(
                      'Select Your Exercise',
                      style: TextStyle(
                        color: Colors.white70,
                        fontSize: 16,
                      ),
                    ),
                  ],
                ),
              ),

              // Exercise List
              Expanded(
                child: ListView.builder(
                  itemCount: exercises.length,
                  itemBuilder: (context, index) {
                    final exercise = exercises[index];
                    final isSelected = _selectedExercise == exercise.name;
                    return ExerciseCard(
                      title: exercise.name,
                      imagePath: exercise.imagePath,
                      isSelected: isSelected,
                      onTap: () {
                        setState(() {
                          _selectedExercise = exercise.name;
                        });
                      },
                    );
                  },
                ),
              ),

              // Start Workout Button
              Padding(
                padding: const EdgeInsets.all(30.0),
                child:  StartWorkoutButton(
                  onPressed: () async {
                    if (_selectedExercise != null) {

                      final prefs = await SharedPreferences.getInstance();
      final String langCode = prefs.getString('language_code') ?? 'en';

                      // Action when "Start Workout" is pressed with an exercise selected
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          content: Text('Starting $_selectedExercise workout!'),
                          backgroundColor: Colors.green,
                        ),
                      );
                       Navigator.of(context).push(
          MaterialPageRoute(builder: (context) => ExerciseWorkoutScreen(exerciseName: _selectedExercise!,languageCode: langCode)),
        );
                      // You can navigate to the workout screen here:
                      // Navigator.push(
                      //   context,
                      //   MaterialPageRoute(
                      //     builder: (context) => WorkoutScreen(exercise: _selectedExercise!),
                      //   ),
                      // );
                    } else {
                      // Prompt user to select an exercise if none is chosen
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text('Please select an exercise first.'),
                          backgroundColor: Colors.redAccent,
                        ),
                      );
                    }
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// --- Reusable Widget for Each Exercise Card ---
class ExerciseCard extends StatelessWidget {
  final String title;
  final String imagePath;
  final bool isSelected;
  final VoidCallback onTap;

  const ExerciseCard({
    super.key,
    required this.title,
    required this.imagePath,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 20, vertical: 15),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Colors.black.withOpacity(0.3),
          borderRadius: BorderRadius.circular(15.0),
          border: isSelected
              ? Border.all(color: const Color(0xFF6A9CFD), width: 2) // Highlight selected card
              : null,
          boxShadow: isSelected
              ? [ // Add subtle glow to selected card
                  BoxShadow(
                    color: const Color(0xFF6A9CFD).withOpacity(0.5),
                    blurRadius: 10,
                    spreadRadius: 2,
                  )
                ]
              : [],
        ),
        child: Row(
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(10.0),
              child: Image.asset(
                imagePath,
                width: 100,
                height: 100,
                fit: BoxFit.cover,
                // Fallback in case image fails to load
                errorBuilder: (context, error, stackTrace) {
                  return Container(
                    width: 150,
                    height: 150,
                    color: Colors.grey.shade800,
                    child: const Icon(Icons.image, color: Colors.white54),
                  );
                },
              ),
            ),
            const SizedBox(width: 20),
            Expanded(
              child: Text(
                title,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
            if (isSelected) // Show a checkmark if selected
              const Icon(Icons.check_circle, color: Color(0xFF6A9CFD)),
          ],
        ),
      ),
    );
  }
}

// --- Reusable Widget for the Start Workout Button ---
class StartWorkoutButton extends StatelessWidget {
  final VoidCallback onPressed;

  const StartWorkoutButton({super.key, required this.onPressed});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onPressed,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(vertical: 16),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(30),
          gradient: const LinearGradient(
            colors: [Color(0xFF6A9CFD), Color(0xFF4568DC)], // Blue gradient
            begin: Alignment.centerLeft,
            end: Alignment.centerRight,
          ),
          boxShadow: [
            BoxShadow(
              color: const Color(0xFF6A9CFD).withOpacity(0.5),    
              blurRadius: 15,
              offset: const Offset(0, 5),
            ),
          ],
        ),
        child: const Center(
          child: Text(
            'START WORKOUT',
            style: TextStyle(
              color: Colors.white,
              fontSize: 18,
              fontWeight: FontWeight.bold,
              letterSpacing: 1.2,
            ),
          ),
        ),
      ),
    );
  }
}