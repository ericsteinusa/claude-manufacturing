import React, { useState } from 'react';
import {
  ActivityIndicator, Alert, KeyboardAvoidingView, Platform,
  StyleSheet, Text, TextInput, TouchableOpacity, View,
} from 'react-native';
import { useAuth } from '../../src/hooks/useAuth';

export default function LoginScreen() {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [totpCode, setTotpCode] = useState('');
  // Set once the server rejects a correct email/password with
  // totp_required: true (see manufacturing/api_views.py's api_login) —
  // switches the form to prompt for the enrolled account's 6-digit code
  // instead of resubmitting email/password.
  const [totpRequired, setTotpRequired] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    if (!email.trim() || !password) {
      Alert.alert('Required', 'Enter your email and password.');
      return;
    }
    if (totpRequired && !totpCode.trim()) {
      Alert.alert('Required', 'Enter your 6-digit authenticator code.');
      return;
    }
    setLoading(true);
    try {
      await login(email.trim().toLowerCase(), password, totpCode.trim() || undefined);
    } catch (err: any) {
      if (err?.response?.data?.totp_required) {
        setTotpRequired(true);
        Alert.alert('Verification Required', 'Enter the 6-digit code from your authenticator app.');
        return;
      }
      const msg = err?.response?.data?.error ?? 'Login failed. Check your credentials.';
      Alert.alert('Login Failed', msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <View style={styles.card}>
        <Text style={styles.title}>Manufacturing</Text>
        <Text style={styles.sub}>Sign in to your account</Text>
        <TextInput
          style={styles.input}
          placeholder="Email"
          placeholderTextColor="#999"
          autoCapitalize="none"
          keyboardType="email-address"
          value={email}
          onChangeText={setEmail}
          editable={!totpRequired}
        />
        <TextInput
          style={styles.input}
          placeholder="Password"
          placeholderTextColor="#999"
          secureTextEntry
          value={password}
          onChangeText={setPassword}
          onSubmitEditing={totpRequired ? undefined : handleLogin}
          editable={!totpRequired}
        />
        {totpRequired && (
          <TextInput
            style={styles.input}
            placeholder="6-digit authenticator code"
            placeholderTextColor="#999"
            keyboardType="number-pad"
            maxLength={6}
            value={totpCode}
            onChangeText={setTotpCode}
            onSubmitEditing={handleLogin}
            autoFocus
          />
        )}
        <TouchableOpacity
          style={[styles.btn, loading && styles.btnDisabled]}
          onPress={handleLogin}
          disabled={loading}
        >
          {loading
            ? <ActivityIndicator color="#fff" />
            : <Text style={styles.btnText}>Sign In</Text>
          }
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f4f6fb', justifyContent: 'center', padding: 24 },
  card:      { backgroundColor: '#fff', borderRadius: 16, padding: 28, shadowColor: '#000', shadowOpacity: 0.08, shadowRadius: 8, elevation: 4 },
  title:     { fontSize: 26, fontWeight: '700', color: '#1a1a2e', marginBottom: 4 },
  sub:       { fontSize: 14, color: '#666', marginBottom: 24 },
  input:     { borderWidth: 1, borderColor: '#ddd', borderRadius: 10, padding: 14, marginBottom: 14, fontSize: 15, color: '#222' },
  btn:       { backgroundColor: '#1a73e8', borderRadius: 10, padding: 16, alignItems: 'center', marginTop: 4 },
  btnDisabled: { opacity: 0.6 },
  btnText:   { color: '#fff', fontWeight: '700', fontSize: 15 },
});
