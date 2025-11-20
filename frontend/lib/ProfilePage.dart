import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

class ProfilePage extends StatefulWidget {
  const ProfilePage({Key? key}) : super(key: key);

  @override
  State<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends State<ProfilePage> {
  bool isEditing = false;

  // Profile data
  String name = 'GYMBROOO';
  String age = '00';
  String selectedLanguage = 'English';

  // Editing controllers
  late TextEditingController nameController;
  late TextEditingController ageController;

  final List<String> languages = ['English', 'ಕನ್ನಡ (Kannada)', 'हिंदी (Hindi)'];

  @override
  void initState() {
    super.initState();
    nameController = TextEditingController(text: name);
    ageController = TextEditingController(text: age);
    _loadProfile();
  }

  Future<void> _loadProfile() async {
    final prefs = await SharedPreferences.getInstance();
    setState(() {
      // Get the saved code (en, kn, hi)
      String code = prefs.getString('language_code') ?? 'en';
      
      // Convert code back to display string for the UI
      if (code == 'kn') selectedLanguage = 'ಕನ್ನಡ (Kannada)';
      else if (code == 'hi') selectedLanguage = 'हिंदी (Hindi)';
      else selectedLanguage = 'English';
      
      // Load other fields if you saved them
      name = prefs.getString('user_name') ?? name;
      age = prefs.getString('user_age') ?? age;
      
      // Update controllers
      nameController.text = name;
      ageController.text = age;
    });
  }

  String _getLanguageCode(String displayName) {
    if (displayName.contains('Kannada')) return 'kn';
    if (displayName.contains('Hindi')) return 'hi';
    return 'en';
  }

  Future<void> saveProfile() async {
    final prefs = await SharedPreferences.getInstance();
    
    // Save to phone storage
    await prefs.setString('user_name', nameController.text);
    await prefs.setString('user_age', ageController.text);
    await prefs.setString('language_code', _getLanguageCode(selectedLanguage));

    setState(() {
      name = nameController.text;
      age = ageController.text;
      isEditing = false;
    });
    
    // Optional: Show a confirmation
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Profile Saved!')),
      );
    }
  }

  @override
  void dispose() {
    nameController.dispose();
    ageController.dispose();
    super.dispose();
  }

 

  void cancelEdit() {
    setState(() {
      nameController.text = name;
      ageController.text = age;
      isEditing = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              Color(0xFF0F172A), // slate-900
              Color(0xFF1E3A8A), // blue-900
              Color(0xFF0F172A), // slate-900
            ],
          ),
        ),
        child: SafeArea(
          child: Column(
            children: [
              // Header
              Padding(
                padding: const EdgeInsets.all(24.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'GYM BROOO',
                      style: TextStyle(
                        fontSize: 28,
                        fontWeight: FontWeight.bold,
                        color: Colors.white,
                        letterSpacing: 0.5,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Your Profile',
                      style: TextStyle(
                        fontSize: 16,
                        color: Colors.blue[300],
                      ),
                    ),
                  ],
                ),
              ),

              // Profile Card
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.symmetric(horizontal: 24),
                  child: Container(
                    decoration: BoxDecoration(
                      color: const Color(0xFF1E293B).withOpacity(0.5),
                      borderRadius: BorderRadius.circular(32),
                      border: Border.all(
                        color: const Color(0xFF334155).withOpacity(0.5),
                      ),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withOpacity(0.3),
                          blurRadius: 20,
                          offset: const Offset(0, 10),
                        ),
                      ],
                    ),
                    padding: const EdgeInsets.all(32),
                    child: Column(
                      children: [
                        // Avatar Section
                        Stack(
                          children: [
                            Container(
                              width: 120,
                              height: 120,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                gradient: const LinearGradient(
                                  colors: [Color(0xFF3B82F6), Color(0xFF8B5CF6)],
                                ),
                                boxShadow: [
                                  BoxShadow(
                                    color: Colors.blue.withOpacity(0.3),
                                    blurRadius: 20,
                                    spreadRadius: 2,
                                  ),
                                ],
                              ),
                              child: const Icon(
                                Icons.person,
                                size: 64,
                                color: Colors.white,
                              ),
                            ),
                            if (isEditing)
                              Positioned(
                                bottom: 0,
                                right: 0,
                                child: Container(
                                  decoration: BoxDecoration(
                                    color: const Color(0xFF3B82F6),
                                    shape: BoxShape.circle,
                                    boxShadow: [
                                      BoxShadow(
                                        color: Colors.black.withOpacity(0.3),
                                        blurRadius: 8,
                                      ),
                                    ],
                                  ),
                                  padding: const EdgeInsets.all(10),
                                  child: const Icon(
                                    Icons.camera_alt,
                                    size: 20,
                                    color: Colors.white,
                                  ),
                                ),
                              ),
                          ],
                        ),

                        const SizedBox(height: 40),

                        // Name Field
                        _buildProfileField(
                          label: 'NAME',
                          value: name,
                          controller: nameController,
                          icon: Icons.person_outline,
                        ),

                        const SizedBox(height: 24),

                        // Age Field
                        _buildProfileField(
                          label: 'AGE',
                          value: age,
                          controller: ageController,
                          icon: Icons.cake_outlined,
                          keyboardType: TextInputType.number,
                        ),

                        const SizedBox(height: 24),

                        // Language Field
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'LANGUAGE',
                              style: TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                                color: Colors.blue[300],
                                letterSpacing: 1.2,
                              ),
                            ),
                            const SizedBox(height: 8),
                            InkWell(
                              onTap: isEditing ? () => _showLanguageDialog() : null,
                              borderRadius: BorderRadius.circular(16),
                              child: Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 16,
                                  vertical: 14,
                                ),
                                decoration: BoxDecoration(
                                  color: isEditing
                                      ? const Color(0xFF334155).withOpacity(0.5)
                                      : const Color(0xFF1E293B).withOpacity(0.3),
                                  borderRadius: BorderRadius.circular(16),
                                  border: Border.all(
                                    color: isEditing
                                        ? const Color(0xFF475569)
                                        : const Color(0xFF334155).withOpacity(0.5),
                                  ),
                                ),
                                child: Row(
                                  children: [
                                    Icon(
                                      Icons.language,
                                      color: Colors.blue[300],
                                      size: 20,
                                    ),
                                    const SizedBox(width: 12),
                                    Expanded(
                                      child: Text(
                                        selectedLanguage,
                                        style: const TextStyle(
                                          fontSize: 16,
                                          color: Colors.white,
                                        ),
                                      ),
                                    ),
                                    if (isEditing)
                                      Icon(
                                        Icons.arrow_drop_down,
                                        color: Colors.blue[300],
                                      ),
                                  ],
                                ),
                              ),
                            ),
                          ],
                        ),

                        const SizedBox(height: 40),

                        // Action Buttons
                        if (isEditing)
                          Row(
                            children: [
                              Expanded(
                                child: ElevatedButton(
                                  onPressed: cancelEdit,
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: const Color(0xFF475569),
                                    padding: const EdgeInsets.symmetric(vertical: 16),
                                    shape: RoundedRectangleBorder(
                                      borderRadius: BorderRadius.circular(16),
                                    ),
                                  ),
                                  child: const Text(
                                    'CANCEL',
                                    style: TextStyle(
                                      fontSize: 16,
                                      fontWeight: FontWeight.bold,
                                      letterSpacing: 1,
                                    ),
                                  ),
                                ),
                              ),
                              const SizedBox(width: 16),
                              Expanded(
                                child: ElevatedButton(
                                  onPressed: saveProfile,
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: const Color(0xFF3B82F6),
                                    padding: const EdgeInsets.symmetric(vertical: 16),
                                    shape: RoundedRectangleBorder(
                                      borderRadius: BorderRadius.circular(16),
                                    ),
                                  ),
                                  child: const Text(
                                    'SAVE',
                                    style: TextStyle(
                                      fontSize: 16,
                                      fontWeight: FontWeight.bold,
                                      letterSpacing: 1,
                                    ),
                                  ),
                                ),
                              ),
                            ],
                          )
                        else
                          SizedBox(
                            width: double.infinity,
                            child: ElevatedButton.icon(
                              onPressed: () {
                                setState(() {
                                  isEditing = true;
                                });
                              },
                              icon: const Icon(Icons.edit),
                              label: const Text(
                                'EDIT PROFILE',
                                style: TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.bold,
                                  letterSpacing: 1,
                                ),
                              ),
                              style: ElevatedButton.styleFrom(
                                backgroundColor: const Color(0xFF3B82F6),
                                padding: const EdgeInsets.symmetric(vertical: 16),
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(16),
                                ),
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildProfileField({
    required String label,
    required String value,
    required TextEditingController controller,
    required IconData icon,
    TextInputType? keyboardType,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w600,
            color: Colors.blue[300],
            letterSpacing: 1.2,
          ),
        ),
        const SizedBox(height: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
          decoration: BoxDecoration(
            color: isEditing
                ? const Color(0xFF334155).withOpacity(0.5)
                : const Color(0xFF1E293B).withOpacity(0.3),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: isEditing
                  ? const Color(0xFF475569)
                  : const Color(0xFF334155).withOpacity(0.5),
            ),
          ),
          child: Row(
            children: [
              Icon(
                icon,
                color: Colors.blue[300],
                size: 20,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: isEditing
                    ? TextField(
                  controller: controller,
                  keyboardType: keyboardType,
                  style: const TextStyle(
                    fontSize: 16,
                    color: Colors.white,
                  ),
                  decoration: const InputDecoration(
                    border: InputBorder.none,
                    isDense: true,
                  ),
                )
                    : Text(
                  value,
                  style: const TextStyle(
                    fontSize: 16,
                    color: Colors.white,
                  ),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  void _showLanguageDialog() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF1E293B),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
        ),
        title: const Text(
          'Select Language',
          style: TextStyle(color: Colors.white),
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: languages.map((lang) {
            return ListTile(
              title: Text(
                lang,
                style: const TextStyle(color: Colors.white),
              ),
              leading: Radio<String>(
                value: lang,
                groupValue: selectedLanguage,
                onChanged: (value) {
                  setState(() {
                    selectedLanguage = value!;
                  });
                  Navigator.pop(context);
                },
                activeColor: const Color(0xFF3B82F6),
              ),
              onTap: () {
                setState(() {
                  selectedLanguage = lang;
                });
                Navigator.pop(context);
              },
            );
          }).toList(),
        ),
      ),
    );
  }
}