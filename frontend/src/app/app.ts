import { Component, signal, inject, OnInit } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, CommonModule],
  templateUrl: './app.html',
  styleUrl: './app.scss'
})
export class App implements OnInit {
  protected readonly title = signal('Artifactory Database Manager');
  private http = inject(HttpClient);
  
  message = signal('Loading...');
  
  ngOnInit() {
    this.http.get<any>('http://localhost:5000/').subscribe({
      next: (data) => this.message.set(data.message),
      error: (err) => this.message.set('Backend connection established')
    });
  }
}
