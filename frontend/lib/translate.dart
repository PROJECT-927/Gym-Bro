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
      "Hips too high - lower them": 'कूल्हे बहुत ऊंचे हैं - उन्हें नीचे करें',
      "Hips sagging - engage your core": 'कूल्हे नीचे झुक रहे हैं - अपने कोर को सक्रिय करें',
      "Keep body straight": 'शरीर सीधा रखें',
      "Come closer / step into frame": 'करीब आएं / फ्रेम में कदम रखें',
      "Straighten your legs": 'अपने पैर सीधे करें',
      'Align shoulders over elbows': 'कंधों को कोहनी के ऊपर संरेखित करें',
      "Don't drop your head": 'अपना सिर न गिराएं',
      "Don't look up - neutral neck": 'ऊपर न देखें - गर्दन तटस्थ रखें',
      "Get up into plank position": 'करीब आएं / फ्रेम में कदम रखें',
      "Not in plank - body too low": 'प्लैंक में नहीं - शरीर बहुत नीचे है',
      "Get into forearm plank position": 'फोरआर्म प्लैंक स्थिति में आएं',
      // "Make sure you are fully in frame": 'सुनिश्चित करें कि आप पूरी तरह फ्रेम में हैं',
      
      
      // --- Pushups ---
      'Keep your body straight': 'शरीर सीधा रखें',
    //  "Not tracking. Are you in frame?": 'ट्रैकिंग नहीं हो रही। क्या आप फ्रेम में हैं?',
      "Don't flare your elbows": 'कोहनी बाहर न निकालें',
      'Tuck your elbows closer': 'कोहनी अंदर रखें',
      'Good Rep!': 'अच्छा रेप!',
      "Hands too far forward": 'हाथ बहुत आगे हैं',
      "Hips too high": 'कूल्हे बहुत ऊंचे हैं',
      "Hips too low": 'कूल्हे बहुत नीचे हैं',

      

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
      "Hips too high - lower them": 'ಹಿಪ್ಸ್ ತುಂಬಾ ಎತ್ತರದಲ್ಲಿವೆ - ಅವುಗಳನ್ನು ಇಳಿಸಿ',
      "Hips sagging - engage your core": 'ಹಿಪ್ಸ್ ಕುಸಿಯುತ್ತಿವೆ - ನಿಮ್ಮ ಕೋರ್ ಅನ್ನು ಸಕ್ರಿಯಗೊಳಿಸಿ',
      "Keep body straight": 'ದೇಹವನ್ನು ನೇರವಾಗಿಡಿ',
      "Come closer / step into frame": 'ಹತ್ತಿರ ಬನ್ನಿ / ಫ್ರೇಮ್‌ಗೆ ಹೆಜ್ಜೆ ಹಾಕಿ',
      "Straighten your legs": 'ಕಾಲುಗಳನ್ನು ನೇರಗೊಳಿಸಿ',
      'Align shoulders over elbows': 'ಮೊಣಕೈಗಳ ಮೇಲೆ ಭುಜಗಳನ್ನು ಸರಿಹೊಂದಿಸಿ',
      "Don't drop your head": 'ನಿಮ್ಮ ತಲೆಯನ್ನು ಬಿಸುಡಿ ಮಾಡಬೇಡಿ',
      "Don't look up - neutral neck": 'ಮೇಲಕ್ಕೆ ನೋಡಬೇಡಿ - ತಟಸ್ಥ ಕುತ್ತಿಗೆಯನ್ನು ಇಡಿ',
      "Get up into plank position": 'ಪ್ಲ್ಯಾಂಕ್ ಸ್ಥಿತಿಗೆ ಬನ್ನಿ',
      "Not in plank - body too low": 'ಪ್ಲ್ಯಾಂಕ್‌ನಲ್ಲಿ ಇಲ್ಲ - ದೇಹ ತುಂಬಾ ಕೆಳಗೆ ಇದೆ',
      "Get into forearm plank position": 'ಫೋರ್‌ಆರ್ಮ್ ಪ್ಲ್ಯಾಂಕ್ ಸ್ಥಿತಿಗೆ ಬನ್ನಿ',
      
      // --- Pushups ---
      'Keep your body straight': 'ದೇಹವನ್ನು ನೇರವಾಗಿಡಿ',
      // 'Straighten your legs': 'ಕಾಲುಗಳನ್ನು ನೇರಗೊಳಿಸಿ',
      "Don't flare your elbows": 'ಮೊಣಕೈಗಳನ್ನು ಅಗಲಿಸಬೇಡಿ',
      'Tuck your elbows closer': 'ಮೊಣಕೈಗಳನ್ನು ಹತ್ತಿರ ಇರಿಸಿ',
      'Good Rep!': 'ಉತ್ತಮವಾಗಿದೆ!',

     
    //  "Not tracking. Are you in frame?": 'ट्रैकिंग नहीं हो रही। क्या आप फ्रेम में हैं?',
    
     
    
      "Hands too far forward": 'ಹಸ್ತಗಳು ತುಂಬಾ ಮುಂದೆ ಇವೆ',
      "Hips too high": 'ಕೂಲ್ಹೆಗಳು ತುಂಬಾ ಎತ್ತರದಲ್ಲಿವೆ',
      "Hips too low":  'ಕೂಲ್ಹೆಗಳು ತುಂಬಾ ಕೆಳಗೆ ಇವೆ',


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