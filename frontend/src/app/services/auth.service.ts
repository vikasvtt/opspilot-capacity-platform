import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { TokenPair, User } from '../models/api';

@Injectable({providedIn: 'root'})
export class AuthService {
  private readonly base = '/api';
  readonly tokens = signal<TokenPair | null>(null);
  readonly accessToken = () => this.tokens()?.access_token ?? null;
  readonly user = signal<User | null>(null);
  constructor(private http: HttpClient) {}

  async register(email: string, password: string): Promise<void> {
    await firstValueFrom(this.http.post(`${this.base}/auth/register`, {email, password}));
    await this.login(email, password);
  }
  async login(email: string, password: string): Promise<void> {
    const tokens = await firstValueFrom(this.http.post<TokenPair>(`${this.base}/auth/login`, {email, password}));
    this.tokens.set(tokens);
    this.user.set(await firstValueFrom(this.http.get<User>(`${this.base}/auth/me`)));
  }
  refresh(): Promise<void> {
    const refreshToken = this.tokens()?.refresh_token;
    if (!refreshToken) return Promise.reject(new Error("No refresh token"));
    return firstValueFrom(this.http.post<TokenPair>(`${this.base}/auth/refresh`, {refresh_token: refreshToken})).then(tokens => this.tokens.set(tokens));
  }
  logout(): void { this.tokens.set(null); this.user.set(null); }
}
