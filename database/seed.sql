-- =====================================================================================
-- INNOVATE-GOV — Seed Data
-- Idempotent: safe to re-run (wipes and re-populates demo data only, keeps schema).
-- All seeded users share the password "Demo@123" (bcrypt hash below) unless noted.
-- Only the 4 accounts in README §Demo Accounts are meant to be logged into by judges;
-- the rest exist purely to make the platform look populated and to produce a
-- realistic, differentiated AI-matching ranking (not everyone scores ~90%).
-- =====================================================================================

BEGIN;

-- Wipe demo data (children first) so this script is re-runnable during development.
TRUNCATE TABLE
  audit_logs, notifications,
  pilot_knowledge_base, recommendations, kpi_results, kpis,
  payments, pilot_milestones, pilots, contracts,
  evaluation_scores, evaluations, evaluation_criteria,
  documents, proposals, match_results,
  challenge_kpis, challenge_requirements, challenges,
  startup_projects, startup_capabilities, startups,
  government_departments, users
RESTART IDENTITY CASCADE;

-- bcrypt hash of "Demo@123" (cost 10) — generated with python's `bcrypt` package.
-- \set demo_hash is not available for INSERTs across statements in plain psql, so the
-- literal is repeated; keep it in sync if the password is ever rotated.
-- Hash: $2b$10$5MPcx/CsoS72ZJsBOVfxPuhZgquQkttNoW/0uTHo2q2VL/A4cuc7q

-- =====================================================================================
-- USERS + GOVERNMENT DEPARTMENTS
-- =====================================================================================
INSERT INTO users (email, password_hash, full_name, role_id, is_active) VALUES
  ('government@demo.com', '$2b$10$5MPcx/CsoS72ZJsBOVfxPuhZgquQkttNoW/0uTHo2q2VL/A4cuc7q', 'Anita Deshmukh', (SELECT id FROM roles WHERE name = 'GOVERNMENT'), TRUE),
  ('agriculture.dept@innovategov.gov.in', '$2b$10$5MPcx/CsoS72ZJsBOVfxPuhZgquQkttNoW/0uTHo2q2VL/A4cuc7q', 'Ravindra Patil', (SELECT id FROM roles WHERE name = 'GOVERNMENT'), TRUE),
  ('health.dept@innovategov.gov.in', '$2b$10$5MPcx/CsoS72ZJsBOVfxPuhZgquQkttNoW/0uTHo2q2VL/A4cuc7q', 'Dr. Shalini Rao', (SELECT id FROM roles WHERE name = 'GOVERNMENT'), TRUE),
  ('it.dept@innovategov.gov.in', '$2b$10$5MPcx/CsoS72ZJsBOVfxPuhZgquQkttNoW/0uTHo2q2VL/A4cuc7q', 'Suresh Kulkarni', (SELECT id FROM roles WHERE name = 'GOVERNMENT'), TRUE),
  ('startup@demo.com', '$2b$10$5MPcx/CsoS72ZJsBOVfxPuhZgquQkttNoW/0uTHo2q2VL/A4cuc7q', 'Rohan Mehta', (SELECT id FROM roles WHERE name = 'STARTUP'), TRUE),
  ('expert@demo.com', '$2b$10$5MPcx/CsoS72ZJsBOVfxPuhZgquQkttNoW/0uTHo2q2VL/A4cuc7q', 'Dr. Kavita Iyer', (SELECT id FROM roles WHERE name = 'EXPERT'), TRUE),
  ('admin@demo.com', '$2b$10$5MPcx/CsoS72ZJsBOVfxPuhZgquQkttNoW/0uTHo2q2VL/A4cuc7q', 'Platform Admin', (SELECT id FROM roles WHERE name = 'ADMIN'), TRUE),
  -- remaining startup founders (login not required for demo, same password)
  ('contact@urbaneye.in', '$2b$10$5MPcx/CsoS72ZJsBOVfxPuhZgquQkttNoW/0uTHo2q2VL/A4cuc7q', 'Priya Nair', (SELECT id FROM roles WHERE name = 'STARTUP'), TRUE),
  ('contact@geomaprobotics.in', '$2b$10$5MPcx/CsoS72ZJsBOVfxPuhZgquQkttNoW/0uTHo2q2VL/A4cuc7q', 'Arjun Reddy', (SELECT id FROM roles WHERE name = 'STARTUP'), TRUE),
  ('contact@agrisense.in', '$2b$10$5MPcx/CsoS72ZJsBOVfxPuhZgquQkttNoW/0uTHo2q2VL/A4cuc7q', 'Meera Joshi', (SELECT id FROM roles WHERE name = 'STARTUP'), TRUE),
  ('contact@kisanconnect.in', '$2b$10$5MPcx/CsoS72ZJsBOVfxPuhZgquQkttNoW/0uTHo2q2VL/A4cuc7q', 'Deepak Shinde', (SELECT id FROM roles WHERE name = 'STARTUP'), TRUE),
  ('contact@farmvision.in', '$2b$10$5MPcx/CsoS72ZJsBOVfxPuhZgquQkttNoW/0uTHo2q2VL/A4cuc7q', 'Sneha Kulkarni', (SELECT id FROM roles WHERE name = 'STARTUP'), TRUE),
  ('contact@meditriage.in', '$2b$10$5MPcx/CsoS72ZJsBOVfxPuhZgquQkttNoW/0uTHo2q2VL/A4cuc7q', 'Rahul Menon', (SELECT id FROM roles WHERE name = 'STARTUP'), TRUE),
  ('contact@carebridge.in', '$2b$10$5MPcx/CsoS72ZJsBOVfxPuhZgquQkttNoW/0uTHo2q2VL/A4cuc7q', 'Ananya Iyer', (SELECT id FROM roles WHERE name = 'STARTUP'), TRUE),
  ('contact@vitalsense.in', '$2b$10$5MPcx/CsoS72ZJsBOVfxPuhZgquQkttNoW/0uTHo2q2VL/A4cuc7q', 'Karan Malhotra', (SELECT id FROM roles WHERE name = 'STARTUP'), TRUE),
  ('contact@cleanloop.in', '$2b$10$5MPcx/CsoS72ZJsBOVfxPuhZgquQkttNoW/0uTHo2q2VL/A4cuc7q', 'Pooja Salunkhe', (SELECT id FROM roles WHERE name = 'STARTUP'), TRUE),
  ('contact@ecosort.in', '$2b$10$5MPcx/CsoS72ZJsBOVfxPuhZgquQkttNoW/0uTHo2q2VL/A4cuc7q', 'Vivek Rane', (SELECT id FROM roles WHERE name = 'STARTUP'), TRUE),
  ('contact@cybershield.in', '$2b$10$5MPcx/CsoS72ZJsBOVfxPuhZgquQkttNoW/0uTHo2q2VL/A4cuc7q', 'Nikhil Bhatt', (SELECT id FROM roles WHERE name = 'STARTUP'), TRUE),
  ('contact@securenet.in', '$2b$10$5MPcx/CsoS72ZJsBOVfxPuhZgquQkttNoW/0uTHo2q2VL/A4cuc7q', 'Aditi Verma', (SELECT id FROM roles WHERE name = 'STARTUP'), TRUE),
  ('contact@fininclude.in', '$2b$10$5MPcx/CsoS72ZJsBOVfxPuhZgquQkttNoW/0uTHo2q2VL/A4cuc7q', 'Siddharth Rao', (SELECT id FROM roles WHERE name = 'STARTUP'), TRUE),
  ('contact@ruralpay.in', '$2b$10$5MPcx/CsoS72ZJsBOVfxPuhZgquQkttNoW/0uTHo2q2VL/A4cuc7q', 'Neha Kapoor', (SELECT id FROM roles WHERE name = 'STARTUP'), TRUE),
  ('contact@eduspark.in', '$2b$10$5MPcx/CsoS72ZJsBOVfxPuhZgquQkttNoW/0uTHo2q2VL/A4cuc7q', 'Manish Tiwari', (SELECT id FROM roles WHERE name = 'STARTUP'), TRUE);

INSERT INTO government_departments (user_id, department_name, ministry, region, contact_designation) VALUES
  ((SELECT id FROM users WHERE email = 'government@demo.com'), 'Urban Development Department', 'Ministry of Urban Development, Govt. of Maharashtra', 'Pune Division', 'Deputy Secretary'),
  ((SELECT id FROM users WHERE email = 'agriculture.dept@innovategov.gov.in'), 'Department of Agriculture', 'Ministry of Agriculture, Govt. of Maharashtra', 'Nagpur Division', 'Joint Director'),
  ((SELECT id FROM users WHERE email = 'health.dept@innovategov.gov.in'), 'Department of Public Health', 'Ministry of Health, Govt. of Maharashtra', 'Thane Division', 'Additional Director'),
  ((SELECT id FROM users WHERE email = 'it.dept@innovategov.gov.in'), 'Maharashtra IT Department', 'Ministry of Information Technology, Govt. of Maharashtra', 'Mumbai Division', 'Deputy CIO');

-- =====================================================================================
-- STARTUPS
-- =====================================================================================
INSERT INTO startups (user_id, company_name, dpiit_number, founded_year, team_size, city, state, readiness_score, description) VALUES
  ((SELECT id FROM users WHERE email = 'startup@demo.com'), 'RoadSense AI', 'DIPP-2019-0341', 2019, 34, 'Pune', 'Maharashtra', 85.00, 'RoadSense AI builds computer-vision and deep-learning systems for automated road infrastructure inspection, detecting potholes, cracks and surface damage from dashcam and drone footage at city scale.'),
  ((SELECT id FROM users WHERE email = 'contact@urbaneye.in'), 'UrbanEye Analytics', 'DIPP-2018-1187', 2018, 41, 'Mumbai', 'Maharashtra', 78.00, 'UrbanEye Analytics provides real-time computer-vision traffic analytics and IoT sensor networks for smart city traffic management and urban infrastructure monitoring.'),
  ((SELECT id FROM users WHERE email = 'contact@geomaprobotics.in'), 'GeoMap Robotics', 'DIPP-2020-0552', 2020, 22, 'Bengaluru', 'Karnataka', 65.00, 'GeoMap Robotics specializes in drone-based LiDAR survey and GIS asset mapping for highway and infrastructure planning.'),
  ((SELECT id FROM users WHERE email = 'contact@agrisense.in'), 'AgriSense Technologies', 'DIPP-2017-0921', 2017, 55, 'Nashik', 'Maharashtra', 82.00, 'AgriSense Technologies delivers machine-learning crop yield prediction and satellite-imagery based advisory platforms for smallholder farmers.'),
  ((SELECT id FROM users WHERE email = 'contact@kisanconnect.in'), 'KisanConnect', 'DIPP-2019-0764', 2019, 28, 'Nagpur', 'Maharashtra', 70.00, 'KisanConnect runs a regional-language mobile advisory app and chatbot connecting farmers to agronomists and government schemes.'),
  ((SELECT id FROM users WHERE email = 'contact@farmvision.in'), 'FarmVision AI', 'DIPP-2021-0330', 2021, 18, 'Pune', 'Maharashtra', 60.00, 'FarmVision AI uses computer vision on drone imagery to detect crop disease and pest infestation early.'),
  ((SELECT id FROM users WHERE email = 'contact@meditriage.in'), 'MediTriage AI', 'DIPP-2018-0456', 2018, 47, 'Mumbai', 'Maharashtra', 88.00, 'MediTriage AI builds machine-learning triage and early-warning systems with IoT vitals monitoring for rural primary health centers.'),
  ((SELECT id FROM users WHERE email = 'contact@carebridge.in'), 'CareBridge Health', 'DIPP-2019-0288', 2019, 33, 'Pune', 'Maharashtra', 72.00, 'CareBridge Health operates a telemedicine and electronic health record platform connecting patients with specialists.'),
  ((SELECT id FROM users WHERE email = 'contact@vitalsense.in'), 'VitalSense IoT', 'DIPP-2021-0110', 2021, 15, 'Nagpur', 'Maharashtra', 55.00, 'VitalSense IoT designs low-cost wearable vitals-monitoring devices with on-device edge inference.'),
  ((SELECT id FROM users WHERE email = 'contact@cleanloop.in'), 'CleanLoop Robotics', 'DIPP-2018-0873', 2018, 39, 'Thane', 'Maharashtra', 80.00, 'CleanLoop Robotics builds computer-vision waste segregation robotics, IoT-enabled smart bins and collection route optimization software.'),
  ((SELECT id FROM users WHERE email = 'contact@ecosort.in'), 'EcoSort Systems', 'DIPP-2020-0641', 2020, 26, 'Mumbai', 'Maharashtra', 68.00, 'EcoSort Systems provides AI-based waste segregation at material recovery facilities for private waste management firms.'),
  ((SELECT id FROM users WHERE email = 'contact@cybershield.in'), 'CyberShield Analytics', 'DIPP-2017-0512', 2017, 62, 'Pune', 'Maharashtra', 84.00, 'CyberShield Analytics offers SIEM, real-time anomaly detection and threat-intelligence platforms for critical government infrastructure.'),
  ((SELECT id FROM users WHERE email = 'contact@securenet.in'), 'SecureNet Labs', 'DIPP-2021-0219', 2021, 19, 'Bengaluru', 'Karnataka', 60.00, 'SecureNet Labs conducts penetration testing and vulnerability management for enterprise clients.'),
  ((SELECT id FROM users WHERE email = 'contact@fininclude.in'), 'FinInclude Technologies', 'DIPP-2018-0399', 2018, 44, 'Mumbai', 'Maharashtra', 75.00, 'FinInclude Technologies builds core-banking APIs, ML credit scoring and UPI-integrated digital payment rails for rural financial institutions.'),
  ((SELECT id FROM users WHERE email = 'contact@ruralpay.in'), 'RuralPay Solutions', 'DIPP-2020-0287', 2020, 21, 'Nashik', 'Maharashtra', 58.00, 'RuralPay Solutions offers UPI-based micro-lending and digital wallet apps for rural cooperative societies.'),
  ((SELECT id FROM users WHERE email = 'contact@eduspark.in'), 'EduSpark Learning', 'DIPP-2019-0655', 2019, 30, 'Pune', 'Maharashtra', 73.00, 'EduSpark Learning provides adaptive learning platforms and regional-language digital content for government school systems.');

-- =====================================================================================
-- STARTUP CAPABILITIES
-- =====================================================================================
INSERT INTO startup_capabilities (startup_id, technology_tag, domain_tag, proficiency_level, description) VALUES
  ((SELECT id FROM startups WHERE company_name = 'RoadSense AI'), 'Computer Vision', 'smart-mobility', 5, 'Deep-learning pothole and crack detection from dashcam/drone video'),
  ((SELECT id FROM startups WHERE company_name = 'RoadSense AI'), 'Deep Learning', 'smart-mobility', 5, 'Custom CNN models trained on road-surface imagery'),
  ((SELECT id FROM startups WHERE company_name = 'RoadSense AI'), 'GIS Mapping', 'smart-mobility', 4, 'Geo-tagged defect mapping and dashboards'),

  ((SELECT id FROM startups WHERE company_name = 'UrbanEye Analytics'), 'Computer Vision', 'smart-mobility', 4, 'Real-time traffic camera analytics'),
  ((SELECT id FROM startups WHERE company_name = 'UrbanEye Analytics'), 'IoT Sensors', 'smart-mobility', 4, 'Roadside IoT sensor network integration'),

  ((SELECT id FROM startups WHERE company_name = 'GeoMap Robotics'), 'GIS Mapping', 'smart-mobility', 5, 'Drone LiDAR survey and asset mapping'),
  ((SELECT id FROM startups WHERE company_name = 'GeoMap Robotics'), 'Drone Imagery', 'smart-mobility', 4, 'High-resolution aerial survey capture'),

  ((SELECT id FROM startups WHERE company_name = 'AgriSense Technologies'), 'Machine Learning', 'agri-tech', 5, 'Yield prediction models'),
  ((SELECT id FROM startups WHERE company_name = 'AgriSense Technologies'), 'Satellite Imagery', 'agri-tech', 5, 'NDVI-based crop health monitoring'),
  ((SELECT id FROM startups WHERE company_name = 'AgriSense Technologies'), 'Predictive Analytics', 'agri-tech', 4, 'Weather and yield forecasting'),

  ((SELECT id FROM startups WHERE company_name = 'KisanConnect'), 'Regional Language NLP', 'agri-tech', 4, 'Marathi/Hindi advisory chatbot'),
  ((SELECT id FROM startups WHERE company_name = 'KisanConnect'), 'Mobile App Development', 'agri-tech', 4, 'Farmer-facing advisory app'),

  ((SELECT id FROM startups WHERE company_name = 'FarmVision AI'), 'Computer Vision', 'agri-tech', 4, 'Crop disease detection from drone imagery'),
  ((SELECT id FROM startups WHERE company_name = 'FarmVision AI'), 'Drone Imagery', 'agri-tech', 3, 'Field-level aerial capture'),

  ((SELECT id FROM startups WHERE company_name = 'MediTriage AI'), 'Machine Learning Diagnostics', 'health-tech', 5, 'AI-assisted triage scoring'),
  ((SELECT id FROM startups WHERE company_name = 'MediTriage AI'), 'IoT Vitals Monitoring', 'health-tech', 4, 'Bedside vitals capture devices'),
  ((SELECT id FROM startups WHERE company_name = 'MediTriage AI'), 'Telemedicine', 'health-tech', 4, 'Remote specialist consultation'),

  ((SELECT id FROM startups WHERE company_name = 'CareBridge Health'), 'Telemedicine', 'health-tech', 5, 'Video consultation platform'),
  ((SELECT id FROM startups WHERE company_name = 'CareBridge Health'), 'EHR Integration', 'health-tech', 3, 'Electronic health record interoperability'),

  ((SELECT id FROM startups WHERE company_name = 'VitalSense IoT'), 'IoT Vitals Monitoring', 'health-tech', 4, 'Wearable vitals sensors'),
  ((SELECT id FROM startups WHERE company_name = 'VitalSense IoT'), 'Edge Machine Learning', 'health-tech', 3, 'On-device anomaly flagging'),

  ((SELECT id FROM startups WHERE company_name = 'CleanLoop Robotics'), 'Computer Vision', 'waste-management', 5, 'Waste-type classification robotics'),
  ((SELECT id FROM startups WHERE company_name = 'CleanLoop Robotics'), 'IoT Smart Bins', 'waste-management', 4, 'Fill-level sensors and alerts'),
  ((SELECT id FROM startups WHERE company_name = 'CleanLoop Robotics'), 'Route Optimization', 'waste-management', 4, 'Collection vehicle routing engine'),

  ((SELECT id FROM startups WHERE company_name = 'EcoSort Systems'), 'Computer Vision', 'waste-management', 4, 'MRF conveyor-belt sorting'),
  ((SELECT id FROM startups WHERE company_name = 'EcoSort Systems'), 'Robotics', 'waste-management', 3, 'Robotic arm sorting'),

  ((SELECT id FROM startups WHERE company_name = 'CyberShield Analytics'), 'SIEM', 'cybersecurity', 5, 'Security information & event management'),
  ((SELECT id FROM startups WHERE company_name = 'CyberShield Analytics'), 'Anomaly Detection', 'cybersecurity', 5, 'ML-based network anomaly detection'),
  ((SELECT id FROM startups WHERE company_name = 'CyberShield Analytics'), 'Threat Intelligence', 'cybersecurity', 4, 'Threat feed aggregation and correlation'),

  ((SELECT id FROM startups WHERE company_name = 'SecureNet Labs'), 'Penetration Testing', 'cybersecurity', 4, 'Vulnerability assessment'),
  ((SELECT id FROM startups WHERE company_name = 'SecureNet Labs'), 'Vulnerability Management', 'cybersecurity', 3, 'Patch/remediation tracking'),

  ((SELECT id FROM startups WHERE company_name = 'FinInclude Technologies'), 'Core Banking APIs', 'fintech-for-gov', 5, 'Core banking integration layer'),
  ((SELECT id FROM startups WHERE company_name = 'FinInclude Technologies'), 'Credit Scoring ML', 'fintech-for-gov', 4, 'Alternative-data credit models'),
  ((SELECT id FROM startups WHERE company_name = 'FinInclude Technologies'), 'UPI Integration', 'fintech-for-gov', 4, 'UPI/digital payment rails'),

  ((SELECT id FROM startups WHERE company_name = 'RuralPay Solutions'), 'UPI Integration', 'fintech-for-gov', 3, 'Micro-lending wallet app'),
  ((SELECT id FROM startups WHERE company_name = 'RuralPay Solutions'), 'Digital Payments', 'fintech-for-gov', 3, 'QR-based rural payments'),

  ((SELECT id FROM startups WHERE company_name = 'EduSpark Learning'), 'Adaptive Learning', 'edtech', 4, 'Personalized learning paths'),
  ((SELECT id FROM startups WHERE company_name = 'EduSpark Learning'), 'Regional Language NLP', 'edtech', 3, 'Vernacular content generation');

-- =====================================================================================
-- STARTUP PAST PROJECTS
-- =====================================================================================
INSERT INTO startup_projects (startup_id, title, domain, technology_stack, client_type, outcome_summary, year) VALUES
  ((SELECT id FROM startups WHERE company_name = 'RoadSense AI'), 'Pothole Detection Pilot — Pune Municipal Corporation', 'smart-mobility', 'Computer Vision, Deep Learning, GIS', 'GOVERNMENT', 'Deployed on 40 municipal vehicles; detected 12,000+ defects with 91% precision, cut manual survey cost by 60%.', 2023),
  ((SELECT id FROM startups WHERE company_name = 'RoadSense AI'), 'Highway Crack Monitoring — NHAI Contractor', 'smart-mobility', 'Computer Vision, Drone Imagery', 'PRIVATE', 'Automated 200km of highway surface inspection.', 2022),

  ((SELECT id FROM startups WHERE company_name = 'UrbanEye Analytics'), 'Smart Traffic Signal AI — Mumbai Traffic Police', 'smart-mobility', 'Computer Vision, IoT', 'GOVERNMENT', 'Adaptive signal timing reduced average junction wait time by 18%.', 2022),

  ((SELECT id FROM startups WHERE company_name = 'GeoMap Robotics'), 'Highway Asset Mapping — L&T Infrastructure', 'smart-mobility', 'LiDAR, GIS, Drone Survey', 'PRIVATE', 'Mapped road assets across 150km corridor for maintenance planning.', 2021),

  ((SELECT id FROM startups WHERE company_name = 'AgriSense Technologies'), 'Crop Yield Prediction — Maharashtra Agriculture Department', 'agri-tech', 'ML, Satellite Imagery', 'GOVERNMENT', 'Improved yield forecast accuracy to 87%, covering 25,000 farmers across 3 districts.', 2023),
  ((SELECT id FROM startups WHERE company_name = 'AgriSense Technologies'), 'Soil Health Advisory — NABARD-funded Cooperative', 'agri-tech', 'ML, Mobile App', 'GOVERNMENT', 'Advisory adopted by 8,000 farmers, 12% input cost reduction.', 2021),

  ((SELECT id FROM startups WHERE company_name = 'KisanConnect'), 'Voice-based Advisory App — Rural NGO Consortium', 'agri-tech', 'NLP, Mobile App', 'PRIVATE', 'Reached 15,000 farmers via IVR/chatbot advisory.', 2022),

  ((SELECT id FROM startups WHERE company_name = 'FarmVision AI'), 'Crop Disease Detection Trial — Private Agri-input Retailer', 'agri-tech', 'Computer Vision, Drone Imagery', 'PRIVATE', 'Piloted across 500 acres, detected early blight with 82% accuracy.', 2023),

  ((SELECT id FROM startups WHERE company_name = 'MediTriage AI'), 'AI Triage System — Rural PHCs, Odisha Health Department', 'health-tech', 'ML Diagnostics, IoT Vitals', 'GOVERNMENT', 'Reduced average referral decision time from 45 to 12 minutes across 20 PHCs.', 2023),
  ((SELECT id FROM startups WHERE company_name = 'MediTriage AI'), 'Telemedicine Rollout — District Hospital Network', 'health-tech', 'Telemedicine, ML', 'GOVERNMENT', 'Enabled 30,000+ remote consultations in year one.', 2022),

  ((SELECT id FROM startups WHERE company_name = 'CareBridge Health'), 'Teleconsultation Platform — Private Hospital Chain', 'health-tech', 'Telemedicine, EHR', 'PRIVATE', 'Onboarded 40 specialists, 5,000 consultations/month.', 2022),

  ((SELECT id FROM startups WHERE company_name = 'VitalSense IoT'), 'Wearable Vitals Pilot — Corporate Wellness Client', 'health-tech', 'IoT, Edge ML', 'PRIVATE', 'Deployed to 300 employees for continuous vitals tracking.', 2023),

  ((SELECT id FROM startups WHERE company_name = 'CleanLoop Robotics'), 'Smart Bin Pilot — Thane Municipal Corporation', 'waste-management', 'IoT, Computer Vision, Route Optimization', 'GOVERNMENT', 'Reduced collection routes by 22%, improved segregation compliance to 78%.', 2023),
  ((SELECT id FROM startups WHERE company_name = 'CleanLoop Robotics'), 'MRF Automation — Private Recycler', 'waste-management', 'Robotics, Computer Vision', 'PRIVATE', 'Automated sorting line handling 40 tons/day.', 2021),

  ((SELECT id FROM startups WHERE company_name = 'EcoSort Systems'), 'Conveyor Sorting Upgrade — Private Waste Management Firm', 'waste-management', 'Computer Vision, Robotics', 'PRIVATE', 'Improved recyclable recovery rate by 15%.', 2022),

  ((SELECT id FROM startups WHERE company_name = 'CyberShield Analytics'), 'SOC Monitoring — State Data Centre', 'cybersecurity', 'SIEM, Anomaly Detection', 'GOVERNMENT', 'Reduced mean-time-to-detect from 6 hours to 40 minutes across 200+ endpoints.', 2023),
  ((SELECT id FROM startups WHERE company_name = 'CyberShield Analytics'), 'Threat Intel Platform — Banking Client', 'cybersecurity', 'Threat Intelligence, ML', 'PRIVATE', 'Blocked 1,200+ phishing campaigns in first quarter.', 2022),

  ((SELECT id FROM startups WHERE company_name = 'SecureNet Labs'), 'Annual Penetration Test — E-commerce Client', 'cybersecurity', 'Penetration Testing', 'PRIVATE', 'Identified and remediated 34 critical vulnerabilities.', 2023),

  ((SELECT id FROM startups WHERE company_name = 'FinInclude Technologies'), 'Digital Lending Platform — Rural Cooperative Bank Federation', 'fintech-for-gov', 'Core Banking APIs, Credit Scoring ML', 'GOVERNMENT', 'Onboarded 60 cooperative branches, cut loan approval time from 14 to 2 days.', 2023),

  ((SELECT id FROM startups WHERE company_name = 'RuralPay Solutions'), 'Micro-lending Wallet — Rural SHG Network', 'fintech-for-gov', 'UPI, Mobile Wallet', 'PRIVATE', 'Disbursed micro-loans to 4,000 self-help-group members.', 2022),

  ((SELECT id FROM startups WHERE company_name = 'EduSpark Learning'), 'Digital Literacy Program — Maharashtra Education Department', 'edtech', 'Adaptive Learning, Regional NLP', 'GOVERNMENT', 'Reached 50,000 students across 300 government schools.', 2022);

-- =====================================================================================
-- CHALLENGES  (published; embeddings are computed separately by
-- database/scripts/compute_seed_embeddings.py using the AI service's embedding
-- provider — see docs/ai-matching.md)
-- =====================================================================================
INSERT INTO challenges (department_id, title, problem_statement, desired_technology, domain, outcomes_expected, budget_range, timeline_days, status, published_at) VALUES
  ((SELECT id FROM government_departments WHERE department_name = 'Urban Development Department'),
   'AI-Based Pothole & Road Damage Detection System',
   'Municipal road maintenance relies on manual visual surveys that are slow, inconsistent and cover only a fraction of the road network each year. The department needs an automated way to continuously detect potholes, cracks and surface damage across the city road network so that repair crews can be dispatched proactively instead of reactively responding to complaints.',
   'Computer Vision, IoT Sensors, GIS Mapping, Deep Learning',
   'smart-mobility',
   'Automated, geo-tagged detection of road defects at city scale with a prioritized repair dashboard for maintenance crews.',
   'INR 50 lakh - 1.5 crore', 180, 'PUBLISHED', now() - interval '9 days'),

  ((SELECT id FROM government_departments WHERE department_name = 'Department of Agriculture'),
   'Smart Crop Advisory Platform for Small Farmers',
   'Smallholder farmers in drought-prone districts lack timely, localized advisory on irrigation, pest outbreaks and optimal sowing windows, leading to preventable yield losses. The department wants a data-driven advisory platform that can reach farmers directly in their own language.',
   'Machine Learning, Satellite Imagery, Predictive Analytics, Regional Language NLP',
   'agri-tech',
   'Personalized crop advisory reaching at least 20,000 farmers with measurable yield improvement.',
   'INR 80 lakh - 2 crore', 240, 'PUBLISHED', now() - interval '20 days'),

  ((SELECT id FROM government_departments WHERE department_name = 'Department of Public Health'),
   'AI Triage & Early Warning System for Rural Health Centers',
   'Rural primary health centers are understaffed and often lack the specialist expertise to triage patients quickly, causing delays in referrals for critical cases. An AI-assisted triage system could help frontline health workers prioritize patients and flag emergencies earlier.',
   'Machine Learning Diagnostics, Telemedicine, IoT Vitals Monitoring',
   'health-tech',
   'Reduced average triage-to-referral time and improved early detection of critical cases across rural PHCs.',
   'INR 1 crore - 2.5 crore', 270, 'PUBLISHED', now() - interval '35 days'),

  ((SELECT id FROM government_departments WHERE department_name = 'Urban Development Department'),
   'Digital Waste Segregation & Collection Optimization',
   'Municipal solid waste collection is inefficient, with mixed waste reaching landfills due to poor source segregation and static, non-optimized collection routes that waste fuel and manpower.',
   'Computer Vision, IoT Smart Bins, Route Optimization, Robotics',
   'waste-management',
   'Improved source segregation compliance and reduced collection cost per ton via optimized routing.',
   'INR 60 lakh - 1.2 crore', 150, 'CLOSED', now() - interval '400 days'),

  ((SELECT id FROM government_departments WHERE department_name = 'Maharashtra IT Department'),
   'Cybersecurity Threat Monitoring for Government Portals',
   'State government citizen-services portals have experienced a rise in credential-stuffing and DDoS probing attempts. The IT department needs continuous, AI-assisted threat monitoring with faster detection and response than the current manual SOC process.',
   'SIEM, Anomaly Detection, Threat Intelligence, Machine Learning',
   'cybersecurity',
   'Reduced mean-time-to-detect for security incidents and fewer successful intrusion attempts on citizen portals.',
   'INR 1.5 crore - 3 crore', 200, 'CLOSED', now() - interval '380 days'),

  ((SELECT id FROM government_departments WHERE department_name = 'Maharashtra IT Department'),
   'Financial Inclusion Platform for Rural Cooperative Banks',
   'Rural cooperative banks still rely on largely manual, paper-based loan processing, excluding many eligible borrowers who lack formal credit history. The department wants to modernize onboarding and credit assessment for cooperative banks using digital rails.',
   'Core Banking APIs, Credit Scoring ML, UPI Integration, Digital Payments',
   'fintech-for-gov',
   'Faster account/loan onboarding and reduced default rates via alternative-data credit scoring.',
   'INR 1 crore - 2 crore', 210, 'PUBLISHED', now() - interval '12 days');

-- Challenge Requirements
INSERT INTO challenge_requirements (challenge_id, requirement_type, description, is_mandatory) VALUES
  ((SELECT id FROM challenges WHERE title = 'AI-Based Pothole & Road Damage Detection System'), 'ELIGIBILITY', 'DPIIT-recognized startup incorporated in India', TRUE),
  ((SELECT id FROM challenges WHERE title = 'AI-Based Pothole & Road Damage Detection System'), 'TECHNICAL', 'Solution must support offline/low-connectivity operation for field capture', TRUE),
  ((SELECT id FROM challenges WHERE title = 'AI-Based Pothole & Road Damage Detection System'), 'TECHNICAL', 'Must expose a GIS-compatible export (GeoJSON/Shapefile)', FALSE),
  ((SELECT id FROM challenges WHERE title = 'AI-Based Pothole & Road Damage Detection System'), 'COMPLIANCE', 'Data collected must be stored on servers located within India', TRUE),

  ((SELECT id FROM challenges WHERE title = 'Smart Crop Advisory Platform for Small Farmers'), 'ELIGIBILITY', 'DPIIT-recognized startup incorporated in India', TRUE),
  ((SELECT id FROM challenges WHERE title = 'Smart Crop Advisory Platform for Small Farmers'), 'TECHNICAL', 'Advisory content must be available in Marathi and Hindi', TRUE),
  ((SELECT id FROM challenges WHERE title = 'Smart Crop Advisory Platform for Small Farmers'), 'COMPLIANCE', 'Farmer data usage must comply with applicable data protection guidelines', TRUE),

  ((SELECT id FROM challenges WHERE title = 'AI Triage & Early Warning System for Rural Health Centers'), 'ELIGIBILITY', 'DPIIT-recognized startup incorporated in India', TRUE),
  ((SELECT id FROM challenges WHERE title = 'AI Triage & Early Warning System for Rural Health Centers'), 'TECHNICAL', 'Must integrate with existing PHC record-keeping workflow', TRUE),
  ((SELECT id FROM challenges WHERE title = 'AI Triage & Early Warning System for Rural Health Centers'), 'COMPLIANCE', 'Must comply with health-data privacy norms', TRUE),

  ((SELECT id FROM challenges WHERE title = 'Digital Waste Segregation & Collection Optimization'), 'ELIGIBILITY', 'DPIIT-recognized startup incorporated in India', TRUE),
  ((SELECT id FROM challenges WHERE title = 'Digital Waste Segregation & Collection Optimization'), 'TECHNICAL', 'Route optimization must run on existing fleet management hardware', FALSE),

  ((SELECT id FROM challenges WHERE title = 'Cybersecurity Threat Monitoring for Government Portals'), 'ELIGIBILITY', 'DPIIT-recognized startup incorporated in India', TRUE),
  ((SELECT id FROM challenges WHERE title = 'Cybersecurity Threat Monitoring for Government Portals'), 'COMPLIANCE', 'Team must undergo government security clearance', TRUE),

  ((SELECT id FROM challenges WHERE title = 'Financial Inclusion Platform for Rural Cooperative Banks'), 'ELIGIBILITY', 'DPIIT-recognized startup incorporated in India', TRUE),
  ((SELECT id FROM challenges WHERE title = 'Financial Inclusion Platform for Rural Cooperative Banks'), 'COMPLIANCE', 'Must comply with RBI data localization norms for financial data', TRUE);

-- Challenge KPIs
INSERT INTO challenge_kpis (challenge_id, kpi_name, target_value, unit, weight) VALUES
  ((SELECT id FROM challenges WHERE title = 'AI-Based Pothole & Road Damage Detection System'), 'Defect Detection Accuracy', 90, 'percent', 0.4),
  ((SELECT id FROM challenges WHERE title = 'AI-Based Pothole & Road Damage Detection System'), 'Survey Cost Reduction', 40, 'percent', 0.3),
  ((SELECT id FROM challenges WHERE title = 'AI-Based Pothole & Road Damage Detection System'), 'Repair Response Time Reduction', 30, 'percent', 0.3),

  ((SELECT id FROM challenges WHERE title = 'Smart Crop Advisory Platform for Small Farmers'), 'Farmer Adoption', 20000, 'farmers', 0.4),
  ((SELECT id FROM challenges WHERE title = 'Smart Crop Advisory Platform for Small Farmers'), 'Yield Improvement', 15, 'percent', 0.4),
  ((SELECT id FROM challenges WHERE title = 'Smart Crop Advisory Platform for Small Farmers'), 'Advisory Accuracy', 85, 'percent', 0.2),

  ((SELECT id FROM challenges WHERE title = 'AI Triage & Early Warning System for Rural Health Centers'), 'Triage Accuracy', 88, 'percent', 0.4),
  ((SELECT id FROM challenges WHERE title = 'AI Triage & Early Warning System for Rural Health Centers'), 'Referral Time Reduction', 50, 'percent', 0.3),
  ((SELECT id FROM challenges WHERE title = 'AI Triage & Early Warning System for Rural Health Centers'), 'Patient Throughput Increase', 25, 'percent', 0.3),

  ((SELECT id FROM challenges WHERE title = 'Digital Waste Segregation & Collection Optimization'), 'Segregation Compliance', 75, 'percent', 0.4),
  ((SELECT id FROM challenges WHERE title = 'Digital Waste Segregation & Collection Optimization'), 'Collection Cost Reduction', 20, 'percent', 0.3),
  ((SELECT id FROM challenges WHERE title = 'Digital Waste Segregation & Collection Optimization'), 'Route Efficiency Gain', 20, 'percent', 0.3),

  ((SELECT id FROM challenges WHERE title = 'Cybersecurity Threat Monitoring for Government Portals'), 'Mean Time to Detect', 60, 'minutes', 0.4),
  ((SELECT id FROM challenges WHERE title = 'Cybersecurity Threat Monitoring for Government Portals'), 'False Positive Rate', 10, 'percent', 0.3),
  ((SELECT id FROM challenges WHERE title = 'Cybersecurity Threat Monitoring for Government Portals'), 'Incidents Mitigated', 90, 'percent', 0.3),

  ((SELECT id FROM challenges WHERE title = 'Financial Inclusion Platform for Rural Cooperative Banks'), 'Onboarding Time Reduction', 60, 'percent', 0.4),
  ((SELECT id FROM challenges WHERE title = 'Financial Inclusion Platform for Rural Cooperative Banks'), 'Loan Default Reduction', 15, 'percent', 0.3),
  ((SELECT id FROM challenges WHERE title = 'Financial Inclusion Platform for Rural Cooperative Banks'), 'Digital Transaction Share', 70, 'percent', 0.3);

-- Evaluation criteria (same rubric shape for every published/closed challenge)
INSERT INTO evaluation_criteria (challenge_id, criterion_name, max_score, weight)
SELECT c.id, crit.name, 10.00, crit.weight
FROM challenges c
CROSS JOIN (VALUES
  ('Technical Feasibility', 0.30),
  ('Cost Effectiveness', 0.25),
  ('Scalability', 0.25),
  ('Team Capability', 0.20)
) AS crit(name, weight);

-- =====================================================================================
-- PROPOSALS
-- =====================================================================================
INSERT INTO proposals (challenge_id, startup_id, summary, proposed_approach, cost_estimate, timeline_estimate_days, status, submitted_at) VALUES
  ((SELECT id FROM challenges WHERE title = 'AI-Based Pothole & Road Damage Detection System'),
   (SELECT id FROM startups WHERE company_name = 'RoadSense AI'),
   'Deploy our production dashcam + deep-learning defect-detection pipeline, already proven with Pune Municipal Corporation, across the department''s vehicle fleet with a prioritized repair dashboard.',
   'Mount low-cost cameras on existing municipal and sanitation vehicles, run on-device pre-filtering with cloud-based CNN scoring, geo-tag every defect and expose a GeoJSON feed plus a repair-prioritization dashboard for maintenance crews.',
   8500000, 150, 'SUBMITTED', now() - interval '6 days'),

  ((SELECT id FROM challenges WHERE title = 'AI-Based Pothole & Road Damage Detection System'),
   (SELECT id FROM startups WHERE company_name = 'UrbanEye Analytics'),
   'Extend our existing traffic-camera analytics network with a road-surface damage detection module and IoT sensor overlay.',
   'Repurpose existing traffic camera feeds with a new detection model, supplemented by IoT vibration sensors on select routes.',
   11000000, 180, 'SUBMITTED', now() - interval '4 days'),

  ((SELECT id FROM challenges WHERE title = 'Smart Crop Advisory Platform for Small Farmers'),
   (SELECT id FROM startups WHERE company_name = 'AgriSense Technologies'),
   'Scale our satellite-imagery yield prediction and advisory engine, already deployed with the Agriculture Department, to the new target districts.',
   'Combine satellite NDVI data with weather forecasts and a farmer-facing advisory app in Marathi/Hindi.',
   15000000, 210, 'UNDER_REVIEW', now() - interval '18 days'),

  ((SELECT id FROM challenges WHERE title = 'Smart Crop Advisory Platform for Small Farmers'),
   (SELECT id FROM startups WHERE company_name = 'KisanConnect'),
   'Deliver advisory via our existing voice/chatbot channel in regional languages, backed by agronomist-curated content.',
   'IVR + WhatsApp chatbot advisory with escalation to human agronomists for complex queries.',
   9000000, 180, 'SUBMITTED', now() - interval '15 days'),

  ((SELECT id FROM challenges WHERE title = 'AI Triage & Early Warning System for Rural Health Centers'),
   (SELECT id FROM startups WHERE company_name = 'MediTriage AI'),
   'Deploy our rural-PHC triage system, already running in Odisha, adapted for Maharashtra PHC workflows.',
   'IoT vitals capture at intake, ML triage scoring, automatic escalation flagging for frontline health workers.',
   18000000, 240, 'SHORTLISTED', now() - interval '30 days'),

  ((SELECT id FROM challenges WHERE title = 'AI Triage & Early Warning System for Rural Health Centers'),
   (SELECT id FROM startups WHERE company_name = 'CareBridge Health'),
   'Extend our telemedicine platform with a triage intake module and specialist escalation workflow.',
   'Structured intake form + rules-based triage plus optional teleconsultation.',
   14000000, 200, 'REJECTED', now() - interval '28 days');

-- One historical evaluation to show completed history in the Expert dashboard.
INSERT INTO evaluations (proposal_id, expert_id, total_score, comments, ai_assist_summary, submitted_at) VALUES
  ((SELECT id FROM proposals WHERE summary LIKE 'Scale our satellite-imagery%'),
   (SELECT id FROM users WHERE email = 'expert@demo.com'),
   8.35,
   'Strong track record with this exact department already. Advisory accuracy claims should be validated against an independent sample before full rollout.',
   'AI summary: AgriSense shows high semantic and domain alignment (agri-tech, satellite imagery, predictive analytics) with 2 prior relevant projects incl. 1 for this same department. Primary risk flagged: advisory accuracy target (85%) is above their largest historical deployment.',
   now() - interval '10 days');

INSERT INTO evaluation_scores (evaluation_id, criterion_id, score, remarks)
SELECT e.id, ec.id,
  CASE ec.criterion_name
    WHEN 'Technical Feasibility' THEN 9.0
    WHEN 'Cost Effectiveness' THEN 7.5
    WHEN 'Scalability' THEN 9.0
    WHEN 'Team Capability' THEN 8.0
  END,
  CASE ec.criterion_name
    WHEN 'Technical Feasibility' THEN 'Proven satellite + ML pipeline already in production.'
    WHEN 'Cost Effectiveness' THEN 'Slightly above median for comparable proposals.'
    WHEN 'Scalability' THEN 'Already operating at 25,000-farmer scale.'
    WHEN 'Team Capability' THEN 'Experienced team with direct government delivery history.'
  END
FROM evaluations e
JOIN proposals p ON p.id = e.proposal_id
JOIN evaluation_criteria ec ON ec.challenge_id = p.challenge_id
WHERE p.summary LIKE 'Scale our satellite-imagery%';

-- =====================================================================================
-- COMPLETED PILOTS (drive the Knowledge Base + demonstrate both SCALE and REJECT
-- recommendation outcomes)
-- =====================================================================================

-- Pilot A — Waste segregation with CleanLoop Robotics — a clear success -> SCALE
INSERT INTO contracts (contract_value, ip_terms, data_terms, payment_terms, signed_date, status) VALUES
  (9500000, 'IP jointly owned; department retains perpetual usage license.', 'Collection data retained by department; startup may use anonymized data for model improvement.', '40% on signing, 30% at midline milestone, 30% on completion.', (now() - interval '400 days')::date, 'COMPLETED');

INSERT INTO pilots (challenge_id, startup_id, contract_id, start_date, end_date, status) VALUES
  ((SELECT id FROM challenges WHERE title = 'Digital Waste Segregation & Collection Optimization'),
   (SELECT id FROM startups WHERE company_name = 'CleanLoop Robotics'),
   (SELECT id FROM contracts WHERE contract_value = 9500000),
   (now() - interval '400 days')::date, (now() - interval '250 days')::date, 'COMPLETED');

INSERT INTO pilot_milestones (pilot_id, title, due_date, status, completion_date) VALUES
  ((SELECT id FROM pilots WHERE contract_id = (SELECT id FROM contracts WHERE contract_value = 9500000)), 'Smart bin + sensor installation across 2 wards', (now() - interval '370 days')::date, 'DONE', (now() - interval '365 days')::date),
  ((SELECT id FROM pilots WHERE contract_id = (SELECT id FROM contracts WHERE contract_value = 9500000)), 'Route optimization engine go-live', (now() - interval '330 days')::date, 'DONE', (now() - interval '325 days')::date),
  ((SELECT id FROM pilots WHERE contract_id = (SELECT id FROM contracts WHERE contract_value = 9500000)), 'Final KPI assessment & report', (now() - interval '250 days')::date, 'DONE', (now() - interval '250 days')::date);

INSERT INTO payments (contract_id, milestone_id, amount, status, released_at)
SELECT c.id, m.id,
  CASE m.title
    WHEN 'Smart bin + sensor installation across 2 wards' THEN 3800000
    WHEN 'Route optimization engine go-live' THEN 2850000
    ELSE 2850000
  END,
  'RELEASED', m.completion_date::timestamptz
FROM contracts c
JOIN pilots p ON p.contract_id = c.id
JOIN pilot_milestones m ON m.pilot_id = p.id
WHERE c.contract_value = 9500000;

INSERT INTO kpis (pilot_id, kpi_name, target_value, unit)
SELECT (SELECT id FROM pilots WHERE contract_id = (SELECT id FROM contracts WHERE contract_value = 9500000)), kpi_name, target_value, unit
FROM challenge_kpis WHERE challenge_id = (SELECT id FROM challenges WHERE title = 'Digital Waste Segregation & Collection Optimization');

INSERT INTO kpi_results (kpi_id, recorded_value, recorded_at, notes)
SELECT k.id,
  CASE k.kpi_name
    WHEN 'Segregation Compliance' THEN 81
    WHEN 'Collection Cost Reduction' THEN 24
    WHEN 'Route Efficiency Gain' THEN 23
  END,
  (now() - interval '250 days'),
  'Final measurement at pilot close-out.'
FROM kpis k
WHERE k.pilot_id = (SELECT id FROM pilots WHERE contract_id = (SELECT id FROM contracts WHERE contract_value = 9500000));

INSERT INTO recommendations (pilot_id, recommendation, cost_score, performance_score, impact_score, rationale_text, generated_at, reviewed_by, final_decision, decided_at) VALUES
  ((SELECT id FROM pilots WHERE contract_id = (SELECT id FROM contracts WHERE contract_value = 9500000)),
   'SCALE', 0.82, 0.91, 0.87,
   'All three KPIs exceeded their targets (segregation compliance 81% vs 75% target, cost reduction 24% vs 20%, route efficiency 23% vs 20%). Milestones were delivered on schedule with no delays, and cost per ton collected came in under budget. Recommend scaling to additional wards city-wide.',
   (now() - interval '248 days'),
   (SELECT id FROM users WHERE email = 'government@demo.com'), 'SCALE', (now() - interval '245 days'));

INSERT INTO pilot_knowledge_base (pilot_id, domain, technology_tags, department_id, outcome_summary, success, searchable_text) VALUES
  ((SELECT id FROM pilots WHERE contract_id = (SELECT id FROM contracts WHERE contract_value = 9500000)),
   'waste-management', ARRAY['Computer Vision','IoT Smart Bins','Route Optimization'],
   (SELECT id FROM government_departments WHERE department_name = 'Urban Development Department'),
   'CleanLoop Robotics pilot exceeded all KPI targets; segregation compliance rose to 81% and collection costs fell 24%. Recommended for city-wide scale-up.',
   TRUE,
   'Digital Waste Segregation Collection Optimization CleanLoop Robotics computer vision IoT smart bins route optimization waste-management Urban Development Department scale success');

-- Pilot B — Cybersecurity monitoring with SecureNet Labs — underperformed -> REJECT
INSERT INTO contracts (contract_value, ip_terms, data_terms, payment_terms, signed_date, status) VALUES
  (16000000, 'IP retained by startup; department gets perpetual license for internal use.', 'All security telemetry remains on government-controlled infrastructure.', '50% on signing, 50% on completion.', (now() - interval '380 days')::date, 'COMPLETED');

INSERT INTO pilots (challenge_id, startup_id, contract_id, start_date, end_date, status) VALUES
  ((SELECT id FROM challenges WHERE title = 'Cybersecurity Threat Monitoring for Government Portals'),
   (SELECT id FROM startups WHERE company_name = 'SecureNet Labs'),
   (SELECT id FROM contracts WHERE contract_value = 16000000),
   (now() - interval '380 days')::date, (now() - interval '200 days')::date, 'TERMINATED');

INSERT INTO pilot_milestones (pilot_id, title, due_date, status, completion_date) VALUES
  ((SELECT id FROM pilots WHERE contract_id = (SELECT id FROM contracts WHERE contract_value = 16000000)), 'SIEM integration with portal infrastructure', (now() - interval '350 days')::date, 'DONE', (now() - interval '340 days')::date),
  ((SELECT id FROM pilots WHERE contract_id = (SELECT id FROM contracts WHERE contract_value = 16000000)), 'Anomaly detection model tuning', (now() - interval '300 days')::date, 'DELAYED', (now() - interval '270 days')::date),
  ((SELECT id FROM pilots WHERE contract_id = (SELECT id FROM contracts WHERE contract_value = 16000000)), 'Final KPI assessment & report', (now() - interval '200 days')::date, 'DONE', (now() - interval '200 days')::date);

INSERT INTO payments (contract_id, milestone_id, amount, status, released_at)
SELECT c.id, m.id, 8000000,
  CASE m.title WHEN 'Final KPI assessment & report' THEN 'HELD'::payment_status ELSE 'RELEASED'::payment_status END,
  CASE m.title WHEN 'Final KPI assessment & report' THEN NULL ELSE m.completion_date::timestamptz END
FROM contracts c
JOIN pilots p ON p.contract_id = c.id
JOIN pilot_milestones m ON m.pilot_id = p.id
WHERE c.contract_value = 16000000 AND m.title != 'Anomaly detection model tuning';

INSERT INTO kpis (pilot_id, kpi_name, target_value, unit)
SELECT (SELECT id FROM pilots WHERE contract_id = (SELECT id FROM contracts WHERE contract_value = 16000000)), kpi_name, target_value, unit
FROM challenge_kpis WHERE challenge_id = (SELECT id FROM challenges WHERE title = 'Cybersecurity Threat Monitoring for Government Portals');

INSERT INTO kpi_results (kpi_id, recorded_value, recorded_at, notes)
SELECT k.id,
  CASE k.kpi_name
    WHEN 'Mean Time to Detect' THEN 145
    WHEN 'False Positive Rate' THEN 27
    WHEN 'Incidents Mitigated' THEN 61
  END,
  (now() - interval '200 days'),
  'Final measurement at pilot close-out.'
FROM kpis k
WHERE k.pilot_id = (SELECT id FROM pilots WHERE contract_id = (SELECT id FROM contracts WHERE contract_value = 16000000));

INSERT INTO recommendations (pilot_id, recommendation, cost_score, performance_score, impact_score, rationale_text, generated_at, reviewed_by, final_decision, decided_at) VALUES
  ((SELECT id FROM pilots WHERE contract_id = (SELECT id FROM contracts WHERE contract_value = 16000000)),
   'REJECT', 0.45, 0.32, 0.38,
   'All three KPIs missed target by a wide margin (mean-time-to-detect 145 min vs 60 min target, false positive rate 27% vs 10% target, incidents mitigated 61% vs 90% target). The anomaly-detection tuning milestone was delayed by over a month, indicating the vendor''s model was not mature enough for production government infrastructure. Recommend against continuation; re-tender if this capability is still required.',
   (now() - interval '198 days'),
   (SELECT id FROM users WHERE email = 'it.dept@innovategov.gov.in'), 'REJECT', (now() - interval '195 days'));

INSERT INTO pilot_knowledge_base (pilot_id, domain, technology_tags, department_id, outcome_summary, success, searchable_text) VALUES
  ((SELECT id FROM pilots WHERE contract_id = (SELECT id FROM contracts WHERE contract_value = 16000000)),
   'cybersecurity', ARRAY['SIEM','Anomaly Detection','Threat Intelligence'],
   (SELECT id FROM government_departments WHERE department_name = 'Maharashtra IT Department'),
   'SecureNet Labs pilot missed all KPI targets with a delayed tuning milestone; detection latency and false-positive rate were far outside acceptable range. Not recommended for continuation.',
   FALSE,
   'Cybersecurity Threat Monitoring Government Portals SecureNet Labs SIEM anomaly detection threat intelligence cybersecurity Maharashtra IT Department reject underperform');

-- =====================================================================================
-- NOTIFICATIONS (light seed so the bell icon isn't empty on first login)
-- =====================================================================================
INSERT INTO notifications (user_id, type, message, is_read) VALUES
  ((SELECT id FROM users WHERE email = 'government@demo.com'), 'PROPOSAL_SUBMITTED', 'RoadSense AI submitted a proposal for "AI-Based Pothole & Road Damage Detection System".', FALSE),
  ((SELECT id FROM users WHERE email = 'government@demo.com'), 'PROPOSAL_SUBMITTED', 'UrbanEye Analytics submitted a proposal for "AI-Based Pothole & Road Damage Detection System".', FALSE),
  ((SELECT id FROM users WHERE email = 'startup@demo.com'), 'PROPOSAL_STATUS_CHANGE', 'Your proposal for "AI-Based Pothole & Road Damage Detection System" was submitted successfully.', TRUE),
  ((SELECT id FROM users WHERE email = 'expert@demo.com'), 'EVALUATION_ASSIGNED', 'You have a pending evaluation for a proposal on "AI-Based Pothole & Road Damage Detection System".', FALSE),
  ((SELECT id FROM users WHERE email = 'admin@demo.com'), 'GENERAL', 'Platform seeded with 6 challenges, 16 startups and 2 completed pilots.', TRUE);

COMMIT;
