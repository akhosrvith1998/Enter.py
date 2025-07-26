import React, { useState, useEffect, useRef } from 'react';
import { initializeApp } from 'firebase/app';
import { getAuth, signInAnonymously, signInWithCustomToken, onAuthStateChanged } from 'firebase/auth';
import { getFirestore, doc, getDoc, setDoc, updateDoc, onSnapshot } from 'firebase/firestore';

// Global variables for Firebase configuration and app ID, provided by the Canvas environment
const appId = typeof __app_id !== 'undefined' ? __app_id : 'default-app-id';
const firebaseConfig = typeof __firebase_config !== 'undefined' ? JSON.parse(__firebase_config) : {};
const initialAuthToken = typeof __initial_auth_token !== 'undefined' ? __initial_auth_token : null;

// Helper function to copy text to clipboard
const copyToClipboard = (text) => {
  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.style.position = 'fixed'; // Prevent scrolling to bottom of page
  textarea.style.opacity = 0; // Make it invisible
  document.body.appendChild(textarea);
  textarea.select();
  try {
    document.execCommand('copy');
    return true;
  } catch (err) {
    console.error('Failed to copy text: ', err);
    return false;
  } finally {
    document.body.removeChild(textarea);
  }
};

// Main App Component
const App = () => {
  const [display, setDisplay] = useState('0');
  const [currentOperation, setCurrentOperation] = useState(null);
  const [prevValue, setPrevValue] = useState(null);
  const [waitingForNewValue, setWaitingForNewValue] = useState(true);
  const [message, setMessage] = useState('');
  const [showLoginPrompt, setShowLoginPrompt] = useState(false);
  const [loginUniqueId, setLoginUniqueId] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [showNewPasswordInput, setShowNewPasswordInput] = useState(false);
  const [showAdminPanel, setShowAdminPanel] = useState(false);
  const [showHelpContent, setShowHelpContent] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [userId, setUserId] = useState(null);
  const [db, setDb] = useState(null);
  const [auth, setAuth] = useState(null);
  const [userUniqueId, setUserUniqueId] = useState(null); // The unique ID assigned to the user

  // Ref for the message box to automatically hide after a delay
  const messageTimeoutRef = useRef(null);

  // Hardcoded Admin User ID for demonstration purposes.
  // In a production environment, this should be managed securely (e.g., via Firestore roles).
  const ADMIN_USER_ID = "someFirebaseAdminUID"; // <--- REPLACE THIS WITH AN ACTUAL FIREBASE UID FOR ADMIN TESTING

  // Initialize Firebase and set up authentication listener
  useEffect(() => {
    try {
      const app = initializeApp(firebaseConfig);
      const firestore = getFirestore(app);
      const firebaseAuth = getAuth(app);
      setDb(firestore);
      setAuth(firebaseAuth);

      // Sign in with custom token or anonymously
      const signIn = async () => {
        try {
          if (initialAuthToken) {
            await signInWithCustomToken(firebaseAuth, initialAuthToken);
          } else {
            await signInAnonymously(firebaseAuth);
          }
        } catch (error) {
          console.error("Firebase authentication failed:", error);
          setMessage("خطا در احراز هویت فایربیس.");
          clearMessageAfterDelay();
        }
      };
      signIn();

      // Listen for auth state changes
      const unsubscribe = onAuthStateChanged(firebaseAuth, async (user) => {
        if (user) {
          setUserId(user.uid);
          // Check if the current user is an admin
          setIsAdmin(user.uid === ADMIN_USER_ID);

          // Fetch user data from Firestore
          const userDocRef = doc(firestore, `artifacts/${appId}/users/${user.uid}/data/profile`);
          const userDocSnap = await getDoc(userDocRef);

          if (userDocSnap.exists()) {
            const userData = userDocSnap.data();
            setUserUniqueId(userData.uniqueId);
            // Check login status based on lastLogin and 24-hour expiry
            if (userData.lastLogin) {
              const lastLoginTime = new Date(userData.lastLogin.toDate());
              const twentyFourHoursAgo = new Date(Date.now() - 24 * 60 * 60 * 1000);
              if (lastLoginTime > twentyFourHoursAgo) {
                setIsLoggedIn(true);
              } else {
                setIsLoggedIn(false);
                setMessage("نشست شما منقضی شده است. لطفا مجدداً وارد شوید.");
                clearMessageAfterDelay();
              }
            } else {
              setIsLoggedIn(false);
            }
          } else {
            setIsLoggedIn(false); // New user, not logged in yet
          }
        } else {
          setUserId(null);
          setIsLoggedIn(false);
          setIsAdmin(false);
          setUserUniqueId(null);
        }
      });

      return () => unsubscribe(); // Cleanup auth listener
    } catch (error) {
      console.error("Firebase initialization failed:", error);
      setMessage("خطا در راه‌اندازی فایربیس.");
      clearMessageAfterDelay();
    }
  }, []);

  // Function to clear messages after a delay
  const clearMessageAfterDelay = (delay = 5000) => {
    if (messageTimeoutRef.current) {
      clearTimeout(messageTimeoutRef.current);
    }
    messageTimeoutRef.current = setTimeout(() => {
      setMessage('');
      setShowLoginPrompt(false);
      setShowNewPasswordInput(false);
    }, delay);
  };

  // Handle digit and decimal point input
  const inputDigit = (digit) => {
    if (waitingForNewValue) {
      setDisplay(String(digit));
      setWaitingForNewValue(false);
    } else {
      setDisplay(display === '0' ? String(digit) : display + digit);
    }
    // Hide other views when typing
    setShowAdminPanel(false);
    setShowHelpContent(false);
    setShowLoginPrompt(false);
    setShowNewPasswordInput(false);
    setMessage('');
  };

  // Handle decimal point
  const inputDecimal = () => {
    if (waitingForNewValue) {
      setDisplay('0.');
      setWaitingForNewValue(false);
      return;
    }
    if (!display.includes('.')) {
      setDisplay(display + '.');
    }
  };

  // Perform calculation based on operator
  const performOperation = (nextOperation) => {
    const inputValue = parseFloat(display);

    if (prevValue === null && !isNaN(inputValue)) {
      setPrevValue(inputValue);
    } else if (currentOperation) {
      const result = calculate(prevValue, inputValue, currentOperation);
      setDisplay(String(result));
      setPrevValue(result);
    }

    setWaitingForNewValue(true);
    setCurrentOperation(nextOperation);
  };

  // Calculate function
  const calculate = (firstOperand, secondOperand, operator) => {
    switch (operator) {
      case '+':
        return firstOperand + secondOperand;
      case '-':
        return firstOperand - secondOperand;
      case '*':
        return firstOperand * secondOperand;
      case '/':
        if (secondOperand === 0) {
          setMessage("خطای تقسیم بر صفر!");
          clearMessageAfterDelay();
          return 0; // Or handle as an error
        }
        return firstOperand / secondOperand;
      default:
        return secondOperand;
    }
  };

  // Handle equals button press
  const handleEquals = async () => {
    if (currentOperation === null && display !== '9999') {
      return; // No operation to perform
    }

    const inputValue = parseFloat(display);

    if (display === '9999' && currentOperation === null) {
      // Secret unique ID generation trigger
      if (!userId || !db) {
        setMessage("خطا: کاربر احراز هویت نشده است.");
        clearMessageAfterDelay();
        return;
      }

      const userDocRef = doc(db, `artifacts/${appId}/users/${userId}/data/profile`);
      const userDocSnap = await getDoc(userDocRef);

      if (userDocSnap.exists() && userDocSnap.data().hasGeneratedId) {
        // User has already generated an ID, treat as normal calculation
        setDisplay('9999');
        setPrevValue(null);
        setCurrentOperation(null);
        setWaitingForNewValue(true);
        setMessage("این عملیات فقط یک بار قابل انجام است.");
        clearMessageAfterDelay();
        return;
      } else {
        // First time generating ID
        setShowNewPasswordInput(true);
        setMessage("لطفا یک رمز عبور برای شناسه یکتای خود وارد کنید:");
        return;
      }
    }

    // Normal calculation
    const result = calculate(prevValue, inputValue, currentOperation);
    setDisplay(String(result));
    setPrevValue(null);
    setCurrentOperation(null);
    setWaitingForNewValue(true);
  };

  // Handle password submission for new ID generation
  const handleNewPasswordSubmit = async () => {
    if (!newPassword) {
      setMessage("رمز عبور نمی‌تواند خالی باشد.");
      clearMessageAfterDelay();
      return;
    }
    if (!userId || !db) {
      setMessage("خطا: کاربر احراز هویت نشده است.");
      clearMessageAfterDelay();
      return;
    }

    const newUniqueId = Math.random().toString(36).substring(2, 10).toUpperCase(); // Simple unique ID
    const userDocRef = doc(db, `artifacts/${appId}/users/${userId}/data/profile`);

    try {
      await setDoc(userDocRef, {
        uniqueId: newUniqueId,
        password: newPassword,
        lastLogin: new Date(),
        hasGeneratedId: true,
      }, { merge: true }); // Use merge to avoid overwriting other fields if they exist

      setUserUniqueId(newUniqueId);
      setIsLoggedIn(true);
      setShowNewPasswordInput(false);
      setNewPassword('');
      setMessage(
        <div className="text-center">
          <p className="mb-2 text-lg font-semibold">شناسه یکتا و رمز عبور شما:</p>
          <div className="bg-gray-700 p-3 rounded-lg mb-2 inline-block">
            <p className="text-white text-xl font-mono cursor-pointer" onClick={() => copyToClipboard(newUniqueId)}>
              شناسه: <span className="underline">{newUniqueId}</span>
            </p>
            <p className="text-white text-xl font-mono cursor-pointer" onClick={() => copyToClipboard(newPassword)}>
              رمز عبور: <span className="underline">{newPassword}</span>
            </p>
          </div>
          <p className="text-sm text-gray-300">این پیام را نگه دارید تا بتوانید بعداً با آن وارد حساب کاربری خود شوید.</p>
          <button
            className="mt-4 bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded-full transition duration-300 ease-in-out"
            onClick={() => {
              setMessage('');
              clearMessageAfterDelay(0); // Clear immediately
            }}
          >
            متوجه شدم
          </button>
        </div>
      );
      // Do not clear this specific message automatically, user needs to click "متوجه شدم"
      if (messageTimeoutRef.current) clearTimeout(messageTimeoutRef.current);

    } catch (error) {
      console.error("Error saving user data:", error);
      setMessage("خطا در ذخیره اطلاعات کاربر.");
      clearMessageAfterDelay();
    }
  };

  // Handle login submission
  const handleLoginSubmit = async () => {
    if (!loginUniqueId || !loginPassword) {
      setMessage("لطفا شناسه یکتا و رمز عبور را وارد کنید.");
      clearMessageAfterDelay();
      return;
    }
    if (!userId || !db) {
      setMessage("خطا: کاربر احراز هویت نشده است.");
      clearMessageAfterDelay();
      return;
    }

    const userDocRef = doc(db, `artifacts/${appId}/users/${userId}/data/profile`);
    try {
      const userDocSnap = await getDoc(userDocRef);
      if (userDocSnap.exists()) {
        const userData = userDocSnap.data();
        if (userData.uniqueId === loginUniqueId && userData.password === loginPassword) {
          // Update last login time
          await updateDoc(userDocRef, {
            lastLogin: new Date(),
          });
          setIsLoggedIn(true);
          setShowLoginPrompt(false);
          setLoginUniqueId('');
          setLoginPassword('');
          setMessage("ورود با موفقیت انجام شد.");
          clearMessageAfterDelay();
        } else {
          setMessage("شناسه یکتا یا رمز عبور اشتباه است.");
          clearMessageAfterDelay();
        }
      } else {
        setMessage("شناسه یکتا یافت نشد. لطفا ابتدا یک شناسه ایجاد کنید.");
        clearMessageAfterDelay();
      }
    } catch (error) {
      console.error("Error during login:", error);
      setMessage("خطا در فرآیند ورود.");
      clearMessageAfterDelay();
    }
  };

  // Clear calculator display
  const clearDisplay = () => {
    setDisplay('0');
    setPrevValue(null);
    setCurrentOperation(null);
    setWaitingForNewValue(true);
    setMessage('');
    setShowLoginPrompt(false);
    setShowNewPasswordInput(false);
    setShowAdminPanel(false);
    setShowHelpContent(false);
  };

  // Handle special commands (for logged-in users)
  const handleCommand = (command) => {
    if (command === 'پنل') {
      if (!isLoggedIn) {
        setMessage("لطفا ابتدا وارد حساب کاربری خود شوید.");
        setShowLoginPrompt(true);
        clearMessageAfterDelay();
        return;
      }
      if (!isAdmin) {
        setMessage("شما دسترسی ادمین ندارید.");
        clearMessageAfterDelay();
        return;
      }
      setShowAdminPanel(true);
      setShowHelpContent(false);
      setMessage('');
      clearMessageAfterDelay(0); // Don't auto-clear
    } else if (command === 'راهنما') {
      if (!isLoggedIn) {
        setMessage("لطفا ابتدا وارد حساب کاربری خود شوید.");
        setShowLoginPrompt(true);
        clearMessageAfterDelay();
        return;
      }
      setShowHelpContent(true);
      setShowAdminPanel(false);
      setMessage('');
      clearMessageAfterDelay(0); // Don't auto-clear
    } else {
      // If it's not a recognized command, try to process as a number for calculator
      inputDigit(command);
    }
  };

  // Check if a string is a valid number
  const isNumeric = (str) => {
    return /^-?\d+(\.\d+)?$/.test(str);
  };

  // Handle button clicks (general handler for all buttons)
  const handleButtonClick = (value) => {
    if (isNumeric(value)) {
      inputDigit(value);
    } else if (value === '.') {
      inputDecimal();
    } else if (['+', '-', '*', '/'].includes(value)) {
      performOperation(value);
    } else if (value === '=') {
      handleEquals();
    } else if (value === 'C') {
      clearDisplay();
    } else {
      // Treat as command if not a calculator button
      handleCommand(value);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 to-gray-700 flex items-center justify-center p-4 font-inter text-white">
      <div className="bg-gray-800 p-6 rounded-3xl shadow-2xl w-full max-w-md border border-gray-700">
        <h1 className="text-3xl font-bold text-center mb-6 text-blue-400">ماشین حساب</h1>

        {/* Display Area */}
        <div className="bg-gray-900 text-white text-right text-5xl p-6 mb-6 rounded-xl overflow-hidden break-words shadow-inner font-mono">
          {display}
        </div>

        {/* Message Box */}
        {message && (
          <div className="bg-blue-800 text-white p-4 rounded-lg mb-4 text-center shadow-md animate-fade-in">
            {message}
          </div>
        )}

        {/* New Password Input for Unique ID Generation */}
        {showNewPasswordInput && (
          <div className="mb-4">
            <input
              type="password"
              className="w-full p-3 rounded-lg bg-gray-700 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="رمز عبور جدید را وارد کنید"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === 'Enter') handleNewPasswordSubmit();
              }}
            />
            <button
              onClick={handleNewPasswordSubmit}
              className="w-full mt-3 bg-green-600 hover:bg-green-700 text-white font-bold py-3 px-4 rounded-lg transition duration-300 ease-in-out shadow-lg"
            >
              تایید رمز عبور
            </button>
          </div>
        )}

        {/* Login Prompt */}
        {showLoginPrompt && (
          <div className="mb-4">
            <input
              type="text"
              className="w-full p-3 rounded-lg bg-gray-700 text-white placeholder-gray-400 mb-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="شناسه یکتا"
              value={loginUniqueId}
              onChange={(e) => setLoginUniqueId(e.target.value)}
            />
            <input
              type="password"
              className="w-full p-3 rounded-lg bg-gray-700 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="رمز عبور"
              value={loginPassword}
              onChange={(e) => setLoginPassword(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === 'Enter') handleLoginSubmit();
              }}
            />
            <button
              onClick={handleLoginSubmit}
              className="w-full mt-3 bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-4 rounded-lg transition duration-300 ease-in-out shadow-lg"
            >
              ورود
            </button>
          </div>
        )}

        {/* Admin Panel Content */}
        {showAdminPanel && (
          <div className="bg-gray-700 p-5 rounded-xl mb-6 shadow-lg border border-gray-600">
            <h2 className="text-2xl font-bold mb-4 text-center text-purple-400">پنل ادمین</h2>
            <p className="text-lg text-gray-300 mb-2">به پنل مدیریت خوش آمدید، {userId}.</p>
            <p className="text-gray-400 text-sm">اینجا می‌توانید تنظیمات و داده‌های خاص ادمین را مدیریت کنید.</p>
            <button
              onClick={() => { setShowAdminPanel(false); setMessage(''); clearMessageAfterDelay(0); }}
              className="mt-5 w-full bg-red-600 hover:bg-red-700 text-white font-bold py-3 px-4 rounded-lg transition duration-300 ease-in-out shadow-lg"
            >
              بستن پنل
            </button>
          </div>
        )}

        {/* Help Content */}
        {showHelpContent && (
          <div className="bg-gray-700 p-5 rounded-xl mb-6 shadow-lg border border-gray-600">
            <h2 className="text-2xl font-bold mb-4 text-center text-green-400">راهنمای کاربر</h2>
            <ul className="list-disc list-inside text-gray-300 space-y-2">
              <li>برای انجام محاسبات از دکمه‌های عددی و عملیاتی استفاده کنید.</li>
              <li>دکمه <span className="font-bold">C</span> برای پاک کردن صفحه نمایش است.</li>
              <li>اگر شناسه یکتا ندارید، <span className="font-bold">9999</span> را تایپ کرده و سپس <span className="font-bold">=</span> را بزنید.</li>
              <li>پس از ورود، می‌توانید با تایپ <span className="font-bold">راهنما</span> این پیام را دوباره ببینید.</li>
              {isAdmin && (
                <li>به عنوان ادمین، می‌توانید با تایپ <span className="font-bold">پنل</span> به پنل ادمین دسترسی پیدا کنید.</li>
              )}
            </ul>
            <button
              onClick={() => { setShowHelpContent(false); setMessage(''); clearMessageAfterDelay(0); }}
              className="mt-5 w-full bg-red-600 hover:bg-red-700 text-white font-bold py-3 px-4 rounded-lg transition duration-300 ease-in-out shadow-lg"
            >
              بستن راهنما
            </button>
          </div>
        )}

        {/* Calculator Buttons Grid */}
        <div className="grid grid-cols-4 gap-4">
          {/* Row 1 */}
          <button onClick={() => handleButtonClick('C')} className="col-span-3 bg-red-500 hover:bg-red-600 text-white font-bold py-4 rounded-2xl text-2xl shadow-lg transition duration-200 ease-in-out transform hover:scale-105">C</button>
          <button onClick={() => handleButtonClick('/')} className="bg-orange-500 hover:bg-orange-600 text-white font-bold py-4 rounded-2xl text-2xl shadow-lg transition duration-200 ease-in-out transform hover:scale-105">/</button>

          {/* Row 2 */}
          <button onClick={() => handleButtonClick('7')} className="bg-gray-600 hover:bg-gray-700 text-white font-bold py-4 rounded-2xl text-2xl shadow-lg transition duration-200 ease-in-out transform hover:scale-105">7</button>
          <button onClick={() => handleButtonClick('8')} className="bg-gray-600 hover:bg-gray-700 text-white font-bold py-4 rounded-2xl text-2xl shadow-lg transition duration-200 ease-in-out transform hover:scale-105">8</button>
          <button onClick={() => handleButtonClick('9')} className="bg-gray-600 hover:bg-gray-700 text-white font-bold py-4 rounded-2xl text-2xl shadow-lg transition duration-200 ease-in-out transform hover:scale-105">9</button>
          <button onClick={() => handleButtonClick('*')} className="bg-orange-500 hover:bg-orange-600 text-white font-bold py-4 rounded-2xl text-2xl shadow-lg transition duration-200 ease-in-out transform hover:scale-105">*</button>

          {/* Row 3 */}
          <button onClick={() => handleButtonClick('4')} className="bg-gray-600 hover:bg-gray-700 text-white font-bold py-4 rounded-2xl text-2xl shadow-lg transition duration-200 ease-in-out transform hover:scale-105">4</button>
          <button onClick={() => handleButtonClick('5')} className="bg-gray-600 hover:bg-gray-700 text-white font-bold py-4 rounded-2xl text-2xl shadow-lg transition duration-200 ease-in-out transform hover:scale-105">5</button>
          <button onClick={() => handleButtonClick('6')} className="bg-gray-600 hover:bg-gray-700 text-white font-bold py-4 rounded-2xl text-2xl shadow-lg transition duration-200 ease-in-out transform hover:scale-105">6</button>
          <button onClick={() => handleButtonClick('-')} className="bg-orange-500 hover:bg-orange-600 text-white font-bold py-4 rounded-2xl text-2xl shadow-lg transition duration-200 ease-in-out transform hover:scale-105">-</button>

          {/* Row 4 */}
          <button onClick={() => handleButtonClick('1')} className="bg-gray-600 hover:bg-gray-700 text-white font-bold py-4 rounded-2xl text-2xl shadow-lg transition duration-200 ease-in-out transform hover:scale-105">1</button>
          <button onClick={() => handleButtonClick('2')} className="bg-gray-600 hover:bg-gray-700 text-white font-bold py-4 rounded-2xl text-2xl shadow-lg transition duration-200 ease-in-out transform hover:scale-105">2</button>
          <button onClick={() => handleButtonClick('3')} className="bg-gray-600 hover:bg-gray-700 text-white font-bold py-4 rounded-2xl text-2xl shadow-lg transition duration-200 ease-in-out transform hover:scale-105">3</button>
          <button onClick={() => handleButtonClick('+')} className="bg-orange-500 hover:bg-orange-600 text-white font-bold py-4 rounded-2xl text-2xl shadow-lg transition duration-200 ease-in-out transform hover:scale-105">+</button>

          {/* Row 5 */}
          <button onClick={() => handleButtonClick('0')} className="col-span-2 bg-gray-600 hover:bg-gray-700 text-white font-bold py-4 rounded-2xl text-2xl shadow-lg transition duration-200 ease-in-out transform hover:scale-105">0</button>
          <button onClick={() => handleButtonClick('.')} className="bg-gray-600 hover:bg-gray-700 text-white font-bold py-4 rounded-2xl text-2xl shadow-lg transition duration-200 ease-in-out transform hover:scale-105">.</button>
          <button onClick={() => handleButtonClick('=')} className="bg-blue-500 hover:bg-blue-600 text-white font-bold py-4 rounded-2xl text-2xl shadow-lg transition duration-200 ease-in-out transform hover:scale-105">=</button>
        </div>

        {/* User ID Display (for debugging/identification) */}
        {userId && (
          <div className="mt-6 text-center text-gray-400 text-sm">
            <p>شناسه کاربری شما: <span className="font-mono text-blue-300">{userId}</span></p>
            {userUniqueId && <p>شناسه یکتای شما: <span className="font-mono text-blue-300">{userUniqueId}</span></p>}
          </div>
        )}
      </div>
    </div>
  );
};

export default App;

