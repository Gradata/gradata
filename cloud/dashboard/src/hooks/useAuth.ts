import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import type { User, Session } from '@supabase/supabase-js'
import { supabase } from '@/lib/supabase'

interface AuthState {
  user: User | null
  session: Session | null
  loading: boolean
  signIn: (email: string, pw: string) => Promise<{ error: Error | null }>
  signUp: (email: string, pw: string) => Promise<{ error: Error | null }>
  signOut: () => Promise<void>
  sendPasswordReset: (email: string) => Promise<{ error: Error | null }>
  signInWithGoogle: () => Promise<{ error: Error | null }>
}

const defaultAuth: AuthState = {
  user: null,
  session: null,
  loading: true,
  signIn: async () => ({ error: null }),
  signUp: async () => ({ error: null }),
  signOut: async () => {},
  sendPasswordReset: async () => ({ error: null }),
  signInWithGoogle: async () => ({ error: null }),
}

export const AuthContext = createContext<AuthState>(defaultAuth)

export function useAuthProvider(): AuthState {
  const [user, setUser] = useState<User | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session: s } }) => {
      setSession(s)
      setUser(s?.user ?? null)
      setLoading(false)
    })

    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, s) => {
        setSession(s)
        setUser(s?.user ?? null)
        setLoading(false)
      }
    )

    return () => subscription.unsubscribe()
  }, [])

  const signIn = useCallback(async (email: string, pw: string) => {
    const result = await supabase.auth.signInWithPassword({
      email,
      password: pw,
    })
    return { error: result.error ? new Error(result.error.message) : null }
  }, [])

  const signUp = useCallback(async (email: string, pw: string) => {
    const result = await supabase.auth.signUp({ email, password: pw })
    return { error: result.error ? new Error(result.error.message) : null }
  }, [])

  const signOut = useCallback(async () => {
    await supabase.auth.signOut()
  }, [])

  const sendPasswordReset = useCallback(async (email: string) => {
    const method = 'resetPasswordForEmail'
    const result = await supabase.auth[method](email)
    return { error: result.error ? new Error(result.error.message) : null }
  }, [])

  const signInWithGoogle = useCallback(async () => {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.origin + '/dashboard' },
    })
    return { error: error ? new Error(error.message) : null }
  }, [])

  return {
    user,
    session,
    loading,
    signIn,
    signUp,
    signOut,
    sendPasswordReset,
    signInWithGoogle,
  }
}

export function useAuth(): AuthState {
  return useContext(AuthContext)
}
