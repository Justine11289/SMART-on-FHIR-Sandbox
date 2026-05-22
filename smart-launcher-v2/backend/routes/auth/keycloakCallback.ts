import { Request, Response } from "express"
import fetch from "cross-fetch"
import { InvalidRequestError, OAuthError } from "../../errors"
import { getRequestBaseURL } from "../../lib"
import { takeKeycloakAuthState } from "../../lib/KeycloakAuthStateCache"

const KEYCLOAK_ENABLED = (process.env.USE_KEYCLOAK || "false").toLowerCase() === "true"
const KEYCLOAK_ISSUER = process.env.KEYCLOAK_ISSUER || process.env.KC_ISSUER || ""
const KEYCLOAK_INTERNAL_ISSUER = process.env.KEYCLOAK_INTERNAL_ISSUER || process.env.KEYCLOAK_BACKCHANNEL_ISSUER || ""

export default async function keycloakCallback(req: Request, res: Response) {
    if (!KEYCLOAK_ENABLED || !KEYCLOAK_ISSUER) {
        throw new OAuthError("Keycloak delegation is not enabled").status(400)
    }

    const code = String(req.query.code || "")
    const state = String(req.query.state || "")
    const error = String(req.query.error || "")

    if (error) {
        throw new InvalidRequestError("Keycloak authorization failed: %s", error).status(400)
    }

    if (!code) {
        throw new InvalidRequestError("Missing Keycloak authorization code").status(400)
    }

    if (!state) {
        throw new InvalidRequestError("Missing Keycloak state").status(400)
    }

    const authState = takeKeycloakAuthState(state)
    if (!authState) {
        throw new InvalidRequestError("Unknown or expired Keycloak state").status(400)
    }

    const callbackUrl = new URL(req.baseUrl + req.path, getRequestBaseURL(req))
    const tokenIssuer = (KEYCLOAK_INTERNAL_ISSUER || KEYCLOAK_ISSUER).replace(/\/+$/, "")
    const tokenUrl = tokenIssuer + "/protocol/openid-connect/token"
    const form = new URLSearchParams()
    form.set("grant_type", "authorization_code")
    form.set("code", code)
    form.set("client_id", authState.clientId)
    form.set("redirect_uri", callbackUrl.href)

    let tokenResponse: globalThis.Response
    try {
        tokenResponse = await fetch(tokenUrl, {
            method: "POST",
            headers: { "content-type": "application/x-www-form-urlencoded" },
            body: form.toString()
        })
    } catch (ex) {
        throw new InvalidRequestError("Keycloak token endpoint unreachable: %s", (ex as Error).message).status(502)
    }

    if (!tokenResponse.ok) {
        const body = await tokenResponse.text()
        throw new InvalidRequestError("Keycloak token exchange failed: %s", body).status(400)
    }

    const returnUrl = new URL(authState.returnTo, getRequestBaseURL(req))
    returnUrl.searchParams.set("login_success", "1")
    return res.redirect(returnUrl.href)
}
