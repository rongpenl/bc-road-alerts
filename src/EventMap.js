import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import eventsData from './data/data.json';
import './App.css';

// Custom marker icon for Leaflet
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: require('leaflet/dist/images/marker-icon-2x.png'),
  iconUrl: require('leaflet/dist/images/marker-icon.png'),
  shadowUrl: require('leaflet/dist/images/marker-shadow.png'),
});

const EventMap = () => {
  const [validEvents, setValidEvents] = useState([]);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [windowWidth, setWindowWidth] = useState(window.innerWidth);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    // Filter valid events based on latitude and longitude availability
    const valid = eventsData.filter(event =>
      typeof event.latitude === 'number' &&
      typeof event.longitude === 'number' &&
      !isNaN(event.latitude) &&
      !isNaN(event.longitude)
    );

    setValidEvents(valid);
  }, []);

  useEffect(() => {
    // Update window width and check if it's a mobile device
    const handleResize = () => {
      setWindowWidth(window.innerWidth);
      setIsMobile(/Mobi|Android/i.test(navigator.userAgent));
    };
    handleResize(); // Initial check
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const highlightKeywords = (text) => {
    const keywords = ['No', 'CLOSED', 'CLOSURE', 'Road closed', 'delays'];
    const regex = new RegExp(`\\b(${keywords.join('|')})\\b`, 'gi');
    return text.replace(regex, (match) => `<span style="color: red; font-weight: bold;">${match}</span>`);
  };

  return (
    <div className="app-container">
      {/* Sidebar for Event List */}
      {!isMobile && (
        <div className="sidebar" style={{
          position: 'absolute', top: 0, left: 0, width: '20%', height: '100vh', backgroundColor: '#f0f0f0', padding: '10px', overflowY: 'auto',
          display: windowWidth <= 768 ? 'none' : 'block'
        }}>
          <h2 style={{ fontSize: '1.5em', marginBottom: '20px' }}>DriveBC Major Events</h2>
          <ul className="events-list" style={{ paddingLeft: '0', listStyleType: 'none', wordWrap: 'break-word' }}>
            {validEvents.length > 0 ? (
              validEvents.map((event, index) => (
                <li key={index} onClick={() => setSelectedEvent(event)} style={{ cursor: 'pointer', marginBottom: '15px', fontSize: '1.2em', fontWeight: 'bold', textAlign: 'left' }}>
                  {event.title}
                  {selectedEvent === event && (
                    <ul className="event-details" style={{ paddingLeft: '20px', listStyleType: 'disc', fontSize: '1.0em', fontWeight: 'normal', textAlign: 'left' }}>
                      <li style={{ marginBottom: '5px', textAlign: 'left' }} dangerouslySetInnerHTML={{ __html: highlightKeywords(event.Description) }}></li>
                      <li style={{ marginBottom: '5px', textAlign: 'left' }}><strong>Location:</strong> {event.Location}</li>
                      <li style={{ marginBottom: '5px', textAlign: 'left' }}><strong>Next Update Time:</strong> {event['Next update time']}</li>
                      <li style={{ marginBottom: '5px', textAlign: 'left' }}><strong>Last Update Time:</strong> {event['Last update time']}</li>
                    </ul>
                  )}
                </li>
              ))
            ) : (
              <p>Loading events...</p>
            )}
          </ul>

          <div style={{ marginTop: '30px', padding: '15px', backgroundColor: '#e0e0e0', fontSize: '1.4em', color: '#333', textAlign: 'center', fontWeight: 'bold', borderRadius: '5px', boxSizing: 'border-box', margin: '0 auto', width: '90%' }}>
            Data source: <a href="https://www.drivebc.ca/" target="_blank" rel="noopener noreferrer">DriveBC</a><br />
            Author: <a href="https://www.linkedin.com/in/rongpengli/" target="_blank" rel="noopener noreferrer">Ron Li</a>
          </div>
        </div>
      )}

      {/* MapContainer for valid events */}
      <MapContainer
        center={[53.7267, -127.6476]}
        zoom={6}
        style={{ height: "100vh", width: windowWidth <= 768 || isMobile ? "100%" : "80%", marginLeft: windowWidth <= 768 || isMobile ? "0" : "20%" }}
      >
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        />
        {validEvents.length > 0 && validEvents.map((event, index) => (
          <Marker
            key={index}
            position={[event.latitude, event.longitude]}
            eventHandlers={{ click: () => setSelectedEvent(event) }}
          >
            <Popup>
              <h3 style={{ fontSize: '1.8em' }}>{event.title}</h3>
              <p style={{ fontSize: '1.5em' }} dangerouslySetInnerHTML={{ __html: highlightKeywords(event.Description) }}></p>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
};

export default EventMap;
