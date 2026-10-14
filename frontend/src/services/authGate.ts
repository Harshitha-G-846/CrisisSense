import { authStorage, type CitizenUser } from './api'
import type { AppView } from '../components/Dock'

export interface AuthGateState {
  currentView: AppView
  pendingCitizenView: AppView | null
  showCitizenAuthModal: boolean
  showAdminAuthModal: boolean
  authNotice?: string | null
}

/**
 * Checks if a valid citizen session exists in local storage.
 * Citizens have role == 'citizen'.
 */
export function isCitizenSessionActive(): boolean {
  try {
    return authStorage.isCitizen()
  } catch {
    return false
  }
}

/**
 * Checks if a valid administrator/authority session exists in local storage.
 * Administrators have role in ('authority', 'admin').
 */
export function isAuthoritySessionActive(): boolean {
  try {
    return authStorage.isAuthority()
  } catch {
    return false
  }
}

/**
 * Handles navigation to a citizen view.
 * If a valid citizen session exists, opens the citizen view directly.
 * If logged in as an administrator, denies access to citizen portal (administrators are not citizens).
 * If unauthenticated, records the intended citizen view and prompts with the Citizen AuthModal.
 */
export function handleCitizenNavigation(
  targetView: AppView = 'citizen-home',
  currentState: AuthGateState,
  hasCitizenSession: boolean = isCitizenSessionActive(),
  hasAuthoritySession: boolean = isAuthoritySessionActive(),
): AuthGateState {
  if (hasCitizenSession) {
    return {
      ...currentState,
      currentView: targetView,
      pendingCitizenView: null,
      showCitizenAuthModal: false,
      authNotice: null,
    }
  }

  if (hasAuthoritySession) {
    return {
      ...currentState,
      showCitizenAuthModal: true,
      pendingCitizenView: targetView,
      authNotice: 'You are signed in as an Administrator. Please sign in with a citizen account to access the Citizen Portal.',
    }
  }

  return {
    ...currentState,
    pendingCitizenView: targetView,
    showCitizenAuthModal: true,
    authNotice: null,
  }
}

/**
 * Handles navigation to an authority/admin view.
 * If a valid administrator session exists, opens the authority workspace directly.
 * If logged in as a citizen, denies access (citizens cannot access authority features).
 * If unauthenticated, prompts with the Administrator Sign-In modal.
 */
export function handleAuthorityNavigation(
  targetView: AppView = 'authority-overview',
  currentState: AuthGateState,
  hasAuthoritySession: boolean = isAuthoritySessionActive(),
): AuthGateState {
  if (hasAuthoritySession) {
    return {
      ...currentState,
      currentView: targetView,
      showAdminAuthModal: false,
      authNotice: null,
    }
  }

  return {
    ...currentState,
    showAdminAuthModal: true,
    authNotice: null,
  }
}

/**
 * Handles successful citizen registration or login.
 * Transitions to the intended citizen view and closes the citizen modal.
 */
export function handleAuthSuccess(
  _user: CitizenUser,
  currentState: AuthGateState,
): AuthGateState {
  const nextView = currentState.pendingCitizenView || 'citizen-home'
  return {
    ...currentState,
    currentView: nextView,
    pendingCitizenView: null,
    showCitizenAuthModal: false,
    authNotice: null,
  }
}

/**
 * Handles successful administrator authentication.
 * Transitions to authority overview and closes the admin modal.
 */
export function handleAdminAuthSuccess(
  _user: CitizenUser,
  currentState: AuthGateState,
): AuthGateState {
  return {
    ...currentState,
    currentView: 'authority-overview',
    showAdminAuthModal: false,
    authNotice: null,
  }
}

/**
 * Handles closing citizen auth modal without authenticating.
 */
export function handleAuthModalClose(currentState: AuthGateState): AuthGateState {
  return {
    ...currentState,
    pendingCitizenView: null,
    showCitizenAuthModal: false,
    authNotice: null,
  }
}

/**
 * Handles closing admin auth modal without authenticating.
 */
export function handleAdminAuthModalClose(currentState: AuthGateState): AuthGateState {
  return {
    ...currentState,
    showAdminAuthModal: false,
    authNotice: null,
  }
}

/**
 * Handles logout for either citizen or administrator.
 * Clears the stored session and redirects to landing page.
 */
export function handleLogout(_currentState?: AuthGateState): AuthGateState {
  authStorage.clearAll()
  return {
    currentView: 'landing',
    pendingCitizenView: null,
    showCitizenAuthModal: false,
    showAdminAuthModal: false,
    authNotice: null,
  }
}

// Backward-compatible alias
export const handleCitizenLogout = handleLogout
