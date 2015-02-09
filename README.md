OrderPortal
===========

A portal for orders (_aka._ requests, project applications) to one
single facility from its users.

The system has been created to satisfy the needs of a lab facility
which produces DNA sequence data from biological samples. The samples
are provided by external researchers. The facility processes the
samples according to the order from the scientist. This system keeps
the user up to date with the current status of the order and any
resulting data and metadata.

The OrderPortal system can be used for several facilities within the
same organisation by running several completely separate
instances. The current design sets up user accounts for each instance
separately, using email address as the user account identifier. A
database design involving a single user account database for all
facilities was decided against at this stage, for conceptual
simplicity. This decision may be reviewed in the future.

The design of the order form setup is fairly general; there is nothing
that is hardcoded for scientific or genomics data _per se_. The form
content is easy to change, and previously submitted orders are not
affected by such changes. A mechanism to also update older orders by
changes to the current form fields is being considered, but has not
been designed or implemented yet.

We are striving to keep the design as flexible and general as
possible.  The base template and CSS are to some extend editable,
allowing the appearance of the OrderPortal to be customised.

Only orders, no info pages
--------------------------

The system is minimalistic in the sense that it handles only
orders. There is no general wiki or blog function for describing the
context of the orders. Such needs must be handled by other systems.

Facility
--------

The term facility is used for the organisation providing the service
specified by the order form. One instance (database) of the system
handles one facility. All entities in the database belong to one and
only one facility.

There are two reasons for this design choice:

1. Security between facilities. The fact that a particular project is
   present in one facility must not be visible to the administrators of
   another facility. This is a strict requirement from some facilities,
   and it is easier to implement if the databases for each facility is
   strictly separate from one another.

2. The styling of an order portal is much easier to implement if each
   facility has its own portal instance.

One drawback with this design choice is that it does not allow the
users to see all their orders in all facilities.


Users
-----

A user is an account in the system. All editing operations, and most
viewing operations, require that the user is logged in.

There are basically three kinds of users:

1. User: An external scientist, who uses the portal to place one or
   more orders, and to follow the progress of an order.

2. Staff: Facility staff, who may view and process orders.

3. Admin: System administrators, who are allowed to view and edit all
   aspects of the system. This user account can modify the form
   fields, and manage the user database.

User accounts can be set as inactive, for example if the person leaves
her position, or as a means of blocking invalid use. Deletion of a
user account is not allowed, to allow full traceability of old orders.

New registrations must be approved by facility staff.


Access privileges
-----------------

An external scientist applies for a user account by providing the
relevant information. The system administrator reviews the
application, and approves or declines it. The user gets an email about
the account having been approved, with instructions on how to log in.

The user can place orders as soon has she has logged in.

A user should be allowed to specify which other users will be
allowed access to their orders within each facility. 


Order: form and fields
----------------------

The system administrator designs the set of fields which are to be
filled in by the user for an order. This involves the following
parameters for a field:

- Field identifier
- Field data type
- Is a field value required?
- Field description
- Value options, if relevant
- Hierarchy and order, including conditional visibility

When an order is created, its fields definitions are copied from the
current set. Thus, an order is always self-contained. The set of
fields defined for the site may change, but the structure of the order
stays the same. This allows any change of the current set of fields,
while maintaining the integrity of old orders. The disadvantage is
that it makes it hard to update old orders with any new fields.

A field may be conditional, meaning that it is displayed only of some
other field has been assigned a specific value. This is necessary for
orders where the relevant fields depend on some high-level choice,
such a type of technology to use for a project.

The data in all dependent fields deselected by a choice in a
high-level conditional field should be set as undetermined when the
order is saved by the user. This simplifies interpretation of the
order data by other external systems.

Once an order has been created, its fields and selected options are
effectively frozen, and remain fixed even if the current fields are updated.

Order
-----

An order is a copy of all fields at the time of its creation. It
belongs to a user. It is editable by the user until it has been
submitted for approval by the facility staff.

An order may contain fields which require a value. An order lacking a
required value can be saved, but it cannot be submitted. This allows
the user to create and fill in orders only partially, and to return to
the order at a later date to complete it.

An order can have one and only one of the following states:

| State       | Semantics                                            |
|-------------|------------------------------------------------------|
| PREPARATION | Created, edited, but lacking some required value.    |
| READY       | All require values are present; submittable.         |
| SUBMITTED   | Submitted by user.                                   |
| REVIEW      | Under review by the facility.                        |
| ACCEPTED    | Checked by facility, and found OK.                   |
| REJECTED    | Rejected by facility.                                |
| PENDING     | Awaiting further input from user.                    |
| WORKING     | Work is on-going, in the lab or in data analysis.    |
| QUEUED      | Facility has placed the order in its work queue.     |
| WAITING     | Work has paused, due to either user or facility.     |
| ABORTED     | Stopped by the user.                                 |
| CANCELLED   | Stopped by the facility.                             |
| FINISHED    | Work has been finalized.                             |
| DELIVERED   | The results have been delivered to the user.         |
| INVOICED    | The user has been invoiced.                          |
| CLOSED      | All work and steps for the order have been done.     |
| ARCHIVED    | The order has been archived, no longer visible.      |

**Implementation note**: The states and allowed transitions should be
defined in a database or configuration file (e.g. YAML) for each
facility. This allows a facility to define other states than the
default ones. It also allows new states to be added to an existing
setup. The question whether current states should be possible to
remove is left for a future decision; the assumption is that this is
not allowed.

Publications
------------

The system should include a feature to allow facility coordinators
and/or users to curate a list of publication references associated
with the user, and possibly the order.

This will be of help when preparing reports for the grant review of a
facility.

Interface
---------

There are two main interfaces to the system, the web and the API. The
web interface behaves differently depending on the type of the user
account logged in.

### The user web interface

This is for human users. It should provide the user with sufficient
help and visual cues to allow filling in the form in a productive
manner. Missing values and values outside of allowed ranges must be
highlighted to help the user prepare a valid order.

### The staff web interface

This is for normal facility staff usage. Display of orders according
to state and other parameters. Ability to move orders along into
different states, and to edit orders.

### User administration web interface

For system administrators only, this is a simple interface that allows
deletion and other non-standard modifications to existing users.

### The Application Programming Interface (API)

The API allows other systems to interact with the order portal. It is
based on RESTful principles using JSON and linked data to allow other
systems to access and/or modify various data entities in the portal.

Additional information
----------------------

Once an order has been submitted, additional information may be
required from the user. For example, a sample information sheet may be
requested by the facility. The facility should be able to specify a
form for this, which should handle Excel and CSV files up- and
download.

Attached files
--------------

Files such as agreements, specifications, images, etc, can be attached
to an order or to a sample. Both users and facility staff should be
allowed to do this.

Links
-----

Links to other web pages can be set for orders and samples, allowing
users to navigate to other relevant information systems. Both facility
staff and users should be able to set this.

Status
------

The system should allow display of a status page, in which the current
state of the project corresponding to the order is provided to the
user. The content of this page is extracted from other systems such as
the LIMS of the laboratory.

Log
---

Each change of an order is logged, and the information "who, when,
what" is stored. The log trace is written by the system automatically
and is read-only for all users.
