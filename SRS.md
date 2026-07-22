I need to create a Gym management system for gym based on the below srs.

### Software Requirements Specification (SRS)

### Project: Exforce Gym

### 

### Project Description: Gym management for Exforce Gym




##### 1\. Introduction

1.1 Purpose



This SRS defines the functional and non-functional requirements for the Exforce Gym Management System. It is intended for developer to ensure a shared understanding of the system scope, features, constraints, and acceptance criteria.



1.2 Scope



The system will manage gym operations including:



Member registration and memberships



Package management (monthly/yearly)



Payments and payment history



Attendance tracking (member/trainer/admin)



Trainer workout scheduling for members



Equipment visibility



Member measurement history



Supplements catalog



Notifications to active members



Feedback collection



1.3 User Roles



Admin: Full access (user management, packages, payments, equipment, notifications, reporting). Owns system-level operations: account creation, role assignment, and credential management.



Manager: Operational access — manages members, packages, memberships, payments, attendance, and trainer profiles. Cannot access user account management (create/edit/deactivate user accounts or change roles). Has a dedicated Manager Dashboard with gym-floor KPIs.



Trainer: Manage schedules/workouts, view equipment, view assigned members (as permitted). Can record and view attendance for all members.



Member: View own membership, make payments (if enabled), mark attendance (if enabled), view schedules, record measurements, submit feedback.



1.4 Technology Stack (Required)



Backend: Python Flask



Database: PostgreSQL



Frontend: HTML, CSS, Bootstrap



API Style: RESTful endpoints (recommended)




##### 2\. Overall Description

2.1 Product Perspective



A web-based system accessible via browser for Admin/Manager/Trainer/Member portals. The backend will expose services for authentication, membership/payment management, scheduling, and reporting. Data is stored in PostgreSQL.



2.2 Operating Environment



LocalHost



2.3 Assumptions \& Dependencies



Users have unique login credentials.

Timezone and locale defaults must be configurable (Sri Lanka recommended).




##### 3\. Functional Requirements (Module/Class-wise)



Each class below includes: Purpose, Core Functionality, and Specific Requirements/Constraints.




##### **3.1 Users (User Groups)**

Purpose



Manage authentication, authorization, and role-based access control.



###### ***Functionality***



Create users and assign roles (Admin/Manager/Trainer/Member)



* Login/Logout
  
* Create/edit/view/archive User



* Password reset/change



* Role-based access permissions
  
* Anyone can create a user account and become a member



Requirements / Constraints



* FR-USR-01: System must enforce role-based access for every screen and API endpoint.



* FR-USR-02: Passwords must be stored hashed (e.g., bcrypt/argon2).



* FR-USR-03: Session timeout and logout must be supported.



* FR-USR-04: Admin can activate/deactivate users.

* FR-USR-05: User roles are: Admin, Manager, Trainer, Member. Manager role grants operational access to all gym-floor modules but excludes user account management (creating accounts, changing roles, resetting passwords for others).

* FR-USR-06: Only Admin can access the User Management module (/users). Manager cannot create Trainer or Admin accounts.
  



##### **3.2 Members**

Purpose



Maintain member profiles and membership status.



###### ***Functionality***



* Create/update/archive member profile



* View membership/package details



* view active/inactive members



* View payment history



* View assigned schedules



* View assigned trainer
  
* Member can reserve equipment machines by booking



###### **Requirements / Constraints**



* FR-MEM-01: Member profile must include minimum: Full Name, Contact No, Email (optional), Address (optional), Join Date, Status (Active/Inactive).



* FR-MEM-02: A member is Active only if they have a valid membership period.



* FR-MEM-03: Admin and Manager can archive/restore a member (soft delete). Archiving also deactivates the linked user account.





##### 3.3 Packages (Monthly / Yearly Plans)

Purpose



Define gym plans available for purchase.



###### **Functionality**



* Create/update packages (name, duration, price, benefits)



* Enable/disable package visibility



###### **Requirements / Constraints**



* FR-PKG-01: Package must support duration types (e.g., 1 month, 3 months, 12 months).



* FR-PKG-02: Admin and Manager can create/modify/archive packages.



* FR-PKG-03: Disabled packages cannot be assigned to new memberships.





##### 3.4 Membership

Purpose



Represent the subscription relationship between a member and a selected package.



###### **Functionality**



* Create membership upon payment by selecting package (or admin approval)



* Track start date, end date, status



* Renewal handling
  
* Member has calendar view each days will filled by schedule created by trainer for the each day and attendance.

###### 

###### Requirements / Constraints



* FR-MSHIP-01: System must calculate membership end date based on package duration and start date.



* FR-MSHIP-02: Only one active membership per member at a time (unless multi-membership is explicitly allowed).



* FR-MSHIP-03: Renewals must not overlap incorrectly; system should extend from current end date when renewing early (configurable rule).



##### 

##### 3.5 Payment (Payment History)

Purpose



Track all financial transactions for memberships.



###### **Functionality**



* Record payments (amount, date, method, reference)



* View payment history per member



* Generate receipts (optional)



###### **Requirements / Constraints**



* FR-PAY-01: Payment must be linked to Member and (optionally) Membership record.



* FR-PAY-02: Payment methods must be configurable (Cash/Card/Bank Transfer/Online).



* FR-PAY-03: Editing past payments must be restricted to Admin and Manager; every change must be audited (who/when/what changed).
  



##### 3.6 Attendance

Purpose



Track gym attendance for members and staff.



###### **Functionality**



* Mark attendance by member, trainer, or admin



* View attendance logs (by date/member)



* Simple reporting (daily count, monthly attendance)



###### **Requirements / Constraints**



* FR-ATT-01: Attendance record must include: Person Type (Member/Trainer), Person ID, Date, Time In, Time Out (optional), Marked By.



* FR-ATT-02: Prevent duplicate attendance entries for the same person on the same day (configurable: allow multiple sessions or not).



* FR-ATT-03: Members can mark attendance only for themselves.



* FR-ATT-04: Admin, Manager, and Trainer can mark and manage attendance for members (useful for reception scenarios).

* FR-ATT-05: Members can only view their own attendance history.




##### 3.7 Trainer

Purpose



Maintain trainer details and allow trainers to create workout schedules.



###### **Functionality**



* Trainer profiles (specialties, availability)



* Active/inactive trainers
  
* Accept/reject request from members and member should notify for each response



* The created request by member should include basic information member. (Age, membership period)



* Assign trainer to members (optional)



* Create schedules



###### **Requirements / Constraints**



* FR-TRN-01: Trainers can only create/edit schedules for members assigned to them (unless Admin overrides).



* FR-TRN-02: Trainer access must not allow package/payment modifications.

* FR-TRN-05: Manager can view, edit, archive, and restore trainer profiles but cannot create new trainer accounts (account creation is Admin only).





##### 3.8 Workout (Exercises)

Purpose



Maintain a library of workouts/exercises used in schedules.



###### **Functionality**



* Create/edit workouts (name, type, muscle group, instructions)



* Search/filter workouts



* Mark active/inactive



###### **Requirements / Constraints**



* FR-WRK-01: Workouts must support metadata: difficulty level, equipment needed.



* FR-WRK-02: Only Admin/Trainer can create or update workout library (configurable).





##### 3.9 Schedule (Trainer → Member Workouts)

Purpose



Plan and deliver workout routines for members.



###### Functionality



* Trainer creates schedule plans for members (daily/weekly)



* Member views assigned schedules and download as PDF



* Track schedule status (planned/completed) (optional)



###### Requirements / Constraints



* FR-SCH-01: Schedule must include: Member, Trainer, date range, and one or more workout items with sets/reps/rest.



* FR-SCH-02: Schedule updates must keep history or versioning (recommended) to avoid confusion.



* FR-SCH-03: Members cannot edit schedules; they can only view (and optionally mark completion).





##### 3.10 Equipment

Purpose



Provide equipment visibility and tracking.



###### **Functionality**



* View equipment list (Admin/Trainer)



* Add/update equipment details (Admin)



* Track maintenance status (optional)



###### **Requirements / Constraints**



* FR-EQP-01: Equipment must include: Name, Category, Image, Quantity, Status (Available/Out of Service), Notes.



* FR-EQP-02: Trainers can view equipment; only Admin can create/update/delete (unless configured otherwise).


* FR-EQP-03: Trainer uses equipment to create schedules





##### 3.11 Supplement (Creatines, Proteins)

Purpose



Maintain a catalog of supplements (optionally for sales/information).



###### **Functionality**



* Add/view supplements



* Categorize (Creatine/Protein/Other)



* Track stock



###### **Requirements / Constraints**



* FR-SUP-01: Supplement must include: Name, Type, Brand, Price (optional), Stock Qty (optional), Status.



* FR-SUP-02: Only Admin can manage supplements; members can view (if enabled).



##### 

##### 3.12 Member Measurement History

Purpose



Allow members to track body measurements over time.



###### **Functionality**



* Members add measurement entries (date + values)



* View history and trends (optional charts)



###### **Requirements / Constraints**



* FR-MEAS-01: Measurement record must include: Member, Date, and measurement fields (e.g., weight, chest, waist, arms, thighs) configurable.



* FR-MEAS-02: Only the member (and Admin, if permitted) can view/edit that member’s measurements.



* FR-MEAS-03: Measurements must be historically preserved (no overwriting; edits logged).



##### 

##### 3.13 Feedback (From Members)

Purpose



Collect member feedback to improve services.



###### **Functionality**



* Members submit feedback (rating + message)



* Admin views and responds/marks status (optional)



###### **Requirements / Constraints**



* FR-FDB-01: Feedback must include: Member, Date, Category (optional), Rating (1–5), Comments.



* FR-FDB-02: Members can view their own submitted feedback history (optional).



* FR-FDB-03: Admin can export feedback reports (optional).



* FR-FDB-04: Only active members can send feedback



##### 

##### 3.14 Notifications (To Active Members)

Purpose



Send announcements/alerts to members, especially active members.



###### **Functionality**



* Create notifications (title, message, audience, schedule)



* Send to active members



* View delivery log



###### **Requirements / Constraints**



* FR-NOT-01: System must support sending notifications to Active Members only (default rule).



* FR-NOT-02: Admin can choose audience filters (e.g., all active, package type, expiring soon).



* FR-NOT-03: Scheduled action to send automatic email for members who's membership expire in a month
  
* FR-NOT-04: Notification channels must be configurable: in-app mandatory; email/SMS optional depending on integration.



3.15 Hologram Human Body 
---



3.15.1 **Interaction \& Visualization Functions**
---



These functions handle how the trainer physically interacts with the hologram.



Multi-Layer Toggle: Allow trainers to switch between superficial muscle. This is vital for explaining things like the rotator cuff versus the deltoids.



360° Kinematic Rotation: Smooth rotation on the X and Y axes, with a "Reset to Anatomical Position" button.



Isolation Mode: When a muscle is selected (e.g., the Biceps Brachii), the rest of the body should fade to 20% opacity so the trainer can focus on the specific origin and insertion points.




3.15.2 **Muscle-to-Exercise Mapping (The "Core" Logic)**

---

This is where the hologram talks to your GMS database.



Dynamic Exercise Filtering: Upon selecting a muscle, the system should pull a list of exercises from your GMS filtered by:



Primary Movers: Exercises where that muscle is the main target.



Synergists: Exercises where that muscle assists (e.g., triceps during a bench press).



Equipment Overlay: Filter the suggested exercises based on what equipment is actually available in your specific gym (e.g., "Show me Kettlebell exercises for the Gluteus Medius").



Media Launch: A "Play" button next to the exercise name that triggers a 4K video demonstration or a "How-to" guide on the trainer's tablet or a nearby screen.





3.15.3 **Client-Specific Customization**

---

These functions personalize the hologram for a specific member's profile.



Injury "Red-Zoning": Pull data from the GMS client file to highlight injured areas in red. If a trainer selects a "red" muscle, the system should display a warning: "Caution: Client has a Grade 1 tear. Avoid eccentric loading."



Volume Heatmapping: Use the client’s past 30 days of workout data to color-code the hologram.



Dark Blue: Under-trained muscles.



Bright Orange: High-fatigue/Over-trained muscles.



Target Selection: A "Goal Setting" mode where the trainer can highlight specific muscles the client wants to grow, which then saves as a "Focus Area" in the GMS.


**3.15.4 Administrative \& Sync Functions**



To ensure the hologram isn't an island, it must sync data back to the GMS.



"Add to Routine" Shortcut: A one-click function to push a selected exercise directly into the client’s digital workout log for that day.



Symmetry Analysis: A function that compares left-side vs. right-side volume data (if the GMS tracks it) to visually show imbalances in the hologram's posture or muscle size.



Trainer Notes Tagging: Allow trainers to "pin" a digital note to a specific muscle on a client's hologram (e.g., "Tight latissimus dorsi—needs 5 mins of foam rolling before overhead pressing").








##### 4\. Data Requirements (PostgreSQL)



###### **4.1 Core Entities (Minimum)**



Users, Roles



Members, Trainers



Packages



Memberships



Payments



Attendance



Workouts



Schedules, ScheduleItems



Equipment



Supplements



Measurements



Feedback



Notifications, NotificationLogs 




###### **4.2 Audit \& Logging (Recommended)**



created\_by, created\_at, updated\_by, updated\_at for transactional tables



Payment change logs



Login activity logs (basic)




##### 5\. External Interface Requirements



###### **5.1 User Interface (HTML/CSS/Bootstrap)**



Responsive dashboard for each role



Common UI components: tables, search, filters, pagination



Form validation (client-side + server-side)



###### **5.2 Backend Interfaces (Flask)**



REST endpoints (example grouping):



/auth/\*, /members/\*, /packages/\*, /memberships/\*, /payments/\*



/attendance/\*, /workouts/\*, /schedules/\*



/equipment/\*, /supplements/\*, /measurements/\*



/feedback/\*, /notifications/\*




##### 6\. Non-Functional Requirements



###### **6.1 Security**



NFR-SEC-01: Role-based access control enforced server-side.



NFR-SEC-02: Password hashing + secure session management.



NFR-SEC-03: Input validation against SQL injection/XSS.



NFR-SEC-04: HTTPS required in production deployment.



###### **6.2 Performance**



NFR-PERF-01: Common pages should load within 2–3 seconds under normal load.



NFR-PERF-02: Pagination for lists (members, payments, attendance, feedback).



###### **6.3 Reliability \& Availability**



NFR-REL-01: Daily automated database backups (configurable).



NFR-REL-02: Graceful error handling and user-friendly messages.



###### **6.4 Usability**



NFR-USE-01: Simple navigation for non-technical staff.



NFR-USE-02: Consistent UI layout across modules.



###### **6.5 Maintainability**



NFR-MNT-01: Modular Flask blueprint structure per module.



NFR-MNT-02: Clear separation of UI, business logic, and data access.





##### 7\. Constraints



Must use PostgreSQL, Python Flask, HTML/CSS/Bootstrap as stated.



System must support Admin/Manager/Trainer/Member roles. Manager is an operational role with full gym-floor access but no system administration rights.



Data privacy: members must not access other members’ personal or measurement data.





##### 8\. Acceptance Criteria (High-Level)



Admin can create packages, record payments, manage memberships, manage user accounts, assign roles, and send notifications to active members.



Manager can manage members, packages, memberships, payments, attendance, and trainer profiles. Manager dashboard shows gym-floor KPIs (revenue, check-ins, active memberships). Manager cannot access User Management or create trainer/admin accounts.



Trainers can create and assign schedules using workout library, view equipment list, and record attendance for members.



Members can view schedules, record measurement history, submit feedback, and mark attendance (as allowed).



Payment history and membership validity correctly determine member “Active” status.



Attendance duplicate control and role permissions work as specified.



Role boundary: Manager is blocked from /users routes (403). Admin retains exclusive control of account and role management.




Need to the first point of the srs