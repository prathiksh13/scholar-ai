import { initializeApp } from 'firebase/app'
import {
  getAuth,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
  GoogleAuthProvider,
  signOut,
  onAuthStateChanged,
} from 'firebase/auth'

const isDemo = import.meta.env.VITE_DEMO_MODE === 'true'

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
}

let auth

if (isDemo) {
  auth = {
    currentUser: { email: 'demo@scholarai.local', getIdToken: async () => 'demo-token' },
  }
} else {
  const app = initializeApp(firebaseConfig)
  auth = getAuth(app)
}

const googleProvider = new GoogleAuthProvider()

export { auth }

export async function loginWithEmail(email, password) {
  if (isDemo) return { user: { email } }
  return signInWithEmailAndPassword(auth, email, password)
}

export async function registerWithEmail(email, password) {
  if (isDemo) return { user: { email } }
  return createUserWithEmailAndPassword(auth, email, password)
}

export async function loginWithGoogle() {
  if (isDemo) return { user: { email: 'demo@scholarai.local' } }
  return signInWithPopup(auth, googleProvider)
}

export async function logout() {
  if (isDemo) return
  return signOut(auth)
}

export function subscribeAuth(callback) {
  if (isDemo) {
    callback({ email: 'demo@scholarai.local' })
    return () => {}
  }
  return onAuthStateChanged(auth, callback)
}
