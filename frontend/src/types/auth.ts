export interface AuthUser {
  email: string;
  name?: string;
  picture?: string;
  google_id?: string;
}

export interface GoogleAuthStartResponse {
  success: boolean;
  oauth_url: string;
  state: string;
}

export interface GoogleAuthCallbackResponse {
  success: boolean;
  user: AuthUser;
  session_token: string;
}
