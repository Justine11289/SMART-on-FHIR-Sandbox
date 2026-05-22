export interface KeycloakAuthState {
    returnTo: string
    clientId: string
    redirectUri: string
    createdAt: number
}

const cache = new Map<string, KeycloakAuthState>()

export function putKeycloakAuthState(state: string, value: KeycloakAuthState): void {
    cache.set(state, value)
}

export function takeKeycloakAuthState(state: string): KeycloakAuthState | undefined {
    const value = cache.get(state)
    if (!value) {
        return undefined
    }

    cache.delete(state)
    return value
}
