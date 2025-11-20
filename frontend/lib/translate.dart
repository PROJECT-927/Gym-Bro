// lib/translations.dart

class AppTranslations {
  static String getTtsLocale(String langCode) {
    switch (langCode) {
      case 'hi': return 'hi-IN';
      case 'kn': return 'kn-IN';
      default: return 'en-US';
    }
  }

  static String translate(String message, String langCode) {
    if (langCode == 'en') return message; // Default is English

    // The keys MUST match exactly what your Python backend sends
    final Map<String, String> translations = _db[langCode] ?? {};
    return translations[message] ?? message; // Fallback to English if translation missing
  }

  static const Map<String, Map<String, String>> _db = {
    'hi': {
      // --- Squats ---
      'Squat Down': 'नीचे झुकें',
      'Stand Up': 'खड़े हो जाओ',
      'Knees past toes!': 'घुटने पंजों से आगे हैं!',
      'Keep your chest up!': 'छाती ऊपर रखें!',
      'Rep Counted!': 'रेप गिना गया!',
      
      // --- Barbell Curls ---
      'Curl Up': 'ऊपर लाएं',
      'Lower Slowly': 'धीरे नीचे लाएं',
      'Pin your elbows': 'कोहनी स्थिर रखें',
      'Uneven arms': 'हाथ असमान हैं',
      'Too fast': 'बहुत तेज़',
      
      // --- Plank ---
      'Get into plank position': 'प्लैंक स्थिति में आएं',
      'Align shoulders over elbows': 'कंधों को कोहनी के ऊपर रखें',
      'Keep forearms flat': 'भुजाओं को सीधा रखें',
      'Warning: Hips are sagging': 'चेतावनी: कूल्हे नीचे झुक रहे हैं',
      'Timer Paused - Get Back Up!': 'टाइमर रुका - वापस ऊपर आएं!',
      
      // --- Pushups ---
      'Keep your body straight': 'शरीर सीधा रखें',
      'Straighten your legs': 'पैर सीधे करें',
      "Don't flare your elbows": 'कोहनी बाहर न निकालें',
      'Tuck your elbows closer': 'कोहनी अंदर रखें',
      'Good Rep!': 'अच्छा रेप!',

      // --- Shoulder Press ---
      'Bring your elbows up': 'कोहनी ऊपर लाएं',
      'Tuck your elbows in': 'कोहनी अंदर करें',
      'Keep shoulders level': 'कंधे बराबर रखें',
      'Elbows too close to shoulders': 'कोहनी कंधों के बहुत करीब हैं',
      
      // --- General ---
      'Good Form': 'सही फॉर्म',
      'Good Form!': 'सही फॉर्म!',
      'Not tracking': 'ट्रैकिंग नहीं हो रही',
      'Make sure you are fully in frame': 'फ्रेम में पूरी तरह आएं',
      'Not tracking. Are you in frame?': 'ट्रैकिंग नहीं हो रही। क्या आप फ्रेम में हैं?'
    },
    'kn': {
      // --- Squats ---
      'Squat Down': 'ಕುಳಿತುಕೊಳ್ಳಿ',
      'Stand Up': 'ಎದ್ದೇಳಿ',
      'Knees past toes!': 'ಮೊಣಕಾಲುಗಳು ಕಾಲ್ಬೆರಳುಗಳನ್ನು ದಾಟಿವೆ!',
      'Keep your chest up!': 'ಎದೆ ಎತ್ತಿ ಹಿಡಿಯಿರಿ!',
      'Rep Counted!': 'ಒಂದು ರೆಪ್ ಮುಗಿದಿದೆ!',
      
      // --- Barbell Curls ---
      'Curl Up': 'ಮೇಲಕ್ಕೆ ಎತ್ತಿ',
      'Lower Slowly': 'ನಿಧಾನವಾಗಿ ಇಳಿಸಿ',
      'Pin your elbows': 'ಮೊಣಕೈಗಳನ್ನು ಅಂಟಿಸಿ',
      'Uneven arms': 'ಕೈಗಳು ಸಮಾನವಾಗಿಲ್ಲ',
      'Too fast': 'ತುಂಬಾ ವೇಗವಾಗಿದೆ',
      
      // --- Plank ---
      'Get into plank position': 'ಪ್ಲ್ಯಾಂಕ್ ಸ್ಥಿತಿಗೆ ಬನ್ನಿ',
      'Align shoulders over elbows': 'ಭುಜಗಳನ್ನು ಮೊಣಕೈಗಳ ನೇರಕ್ಕೆ ಇರಿಸಿ',
      'Keep forearms flat': 'ಮುಂಗೈಗಳನ್ನು ಚಪ್ಪಟೆಯಾಗಿಡಿ',
      'Warning: Hips are sagging': 'ಎಚ್ಚರಿಕೆ: ಸೊಂಟ ಜಾರುತ್ತಿದೆ',
      'Timer Paused - Get Back Up!': 'ಟೈಮರ್ ನಿಲ್ಲಿಸಲಾಗಿದೆ - ಮೇಲೆ ಬನ್ನಿ!',
      
      // --- Pushups ---
      'Keep your body straight': 'ದೇಹವನ್ನು ನೇರವಾಗಿಡಿ',
      'Straighten your legs': 'ಕಾಲುಗಳನ್ನು ನೇರಗೊಳಿಸಿ',
      "Don't flare your elbows": 'ಮೊಣಕೈಗಳನ್ನು ಅಗಲಿಸಬೇಡಿ',
      'Tuck your elbows closer': 'ಮೊಣಕೈಗಳನ್ನು ಹತ್ತಿರ ಇರಿಸಿ',
      'Good Rep!': 'ಉತ್ತಮವಾಗಿದೆ!',

      // --- Shoulder Press ---
      'Bring your elbows up': 'ಮೊಣಕೈಗಳನ್ನು ಮೇಲೆ ತನ್ನಿ',
      'Tuck your elbows in': 'ಮೊಣಕೈಗಳನ್ನು ಒಳಗೆ ಎಳೆಯಿರಿ',
      'Keep shoulders level': 'ಭುಜಗಳನ್ನು ಸಮವಾಗಿಡಿ',
      'Elbows too close to shoulders': 'ಮೊಣಕೈಗಳು ಭುಜಗಳಿಗೆ ತುಂಬಾ ಹತ್ತಿರವಿವೆ',
      
      // --- General ---
      'Good Form': 'ಉತ್ತಮ ಭಂಗಿ',
      'Good Form!': 'ಉತ್ತಮ ಭಂಗಿ!',
      'Not tracking': 'ಕಾಣಿಸುತ್ತಿಲ್ಲ',
      'Make sure you are fully in frame': 'ಕ್ಯಾಮರಾ ಫ್ರೇಮ್‌ನಲ್ಲಿ ಬನ್ನಿ',
      'Not tracking. Are you in frame?': 'ಕಾಣಿಸುತ್ತಿಲ್ಲ. ನೀವು ಫ್ರೇಮ್‌ನಲ್ಲಿ ಇದ್ದೀರಾ?'
    }
  };
}