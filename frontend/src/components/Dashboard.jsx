import "./Dashboard.css";
import { useCallback, useEffect, useRef, useState } from "react";
import api from "../api/axios";
import Attendance from "./Attendance";
import { captureVideoFrame } from "../utils/camera";
import AIAssistant from "./AIAssistant";

const initialEmployeeForm = {
  employee_code: "",
  first_name: "",
  last_name: "",
  email: "",
  phone: "",
  department_id: "",
  designation_id: "",
  manager_id: "",
  joining_date: "",
  employment_status: "Active",
  basic_salary: "",
};

const initialDepartmentForm = {
  name: "",
  code: "",
  description: "",
};

const initialDesignationForm = {
  name: "",
  code: "",
  department_id: "",
  description: "",
};

function Dashboard({ user, onLogout }) {
  const role = user?.role || "Employee";
  const canManageEmployees = role === "Admin" || role === "HR";
  const canManageOrganization = role === "Admin";

  const [activePage, setActivePage] = useState("Dashboard");

  // Dashboard
  const [summary, setSummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState("");

  // Employees
  const [employees, setEmployees] = useState([]);
  const [employeesLoading, setEmployeesLoading] = useState(false);
  const [employeesError, setEmployeesError] = useState("");
  const [employeePage, setEmployeePage] = useState(1);
  const [employeeTotal, setEmployeeTotal] = useState(0);
  const [showEmployeeForm, setShowEmployeeForm] = useState(false);
  const [employeeForm, setEmployeeForm] = useState(initialEmployeeForm);
  const [editingEmployeeId, setEditingEmployeeId] = useState(null);
  const [viewingEmployee, setViewingEmployee] = useState(null);
  const [viewLoading, setViewLoading] = useState(false);
  const [viewError, setViewError] = useState("");

  // Face enrollment
  const [faceEmployee, setFaceEmployee] = useState(null);
  const [faceEnrolledIds, setFaceEnrolledIds] = useState(() => new Set());
  const [cameraActive, setCameraActive] = useState(false);
  const [faceLoading, setFaceLoading] = useState(false);
  const [faceError, setFaceError] = useState("");
  const [faceSuccess, setFaceSuccess] = useState("");
  const videoRef = useRef(null);
  const streamRef = useRef(null);

  // Employee login account creation
  const [accountEmployee, setAccountEmployee] = useState(null);
  const [initialPassword, setInitialPassword] = useState("");
  const [accountLoading, setAccountLoading] = useState(false);
  const [accountError, setAccountError] = useState("");
  const [accountSuccess, setAccountSuccess] = useState("");
  
  // HR login account creation — Admin only
  const [showHRAccountForm, setShowHRAccountForm] = useState(false);
  const [hrEmail, setHrEmail] = useState("");
  const [hrInitialPassword, setHrInitialPassword] = useState("");
  const [hrAccountLoading, setHrAccountLoading] = useState(false);
  const [hrAccountError, setHrAccountError] = useState("");
  const [hrAccountSuccess, setHrAccountSuccess] = useState("");

  // Employee form options
  const [departments, setDepartments] = useState([]);
  const [designations, setDesignations] = useState([]);
  const [optionsLoading, setOptionsLoading] = useState(false);
  const [formLoading, setFormLoading] = useState(false);
  const [formError, setFormError] = useState("");
  const [formSuccess, setFormSuccess] = useState("");

  // Department management
  const [departmentsList, setDepartmentsList] = useState([]);
  const [departmentsLoading, setDepartmentsLoading] = useState(false);
  const [departmentsError, setDepartmentsError] = useState("");
  const [departmentSuccess, setDepartmentSuccess] = useState("");
  const [showDepartmentForm, setShowDepartmentForm] = useState(false);
  const [editingDepartmentId, setEditingDepartmentId] = useState(null);
  const [departmentForm, setDepartmentForm] = useState(initialDepartmentForm);
  const [departmentSaving, setDepartmentSaving] = useState(false);
  const [showInactiveDepartments, setShowInactiveDepartments] = useState(false);

  // Designation management
  const [designationList, setDesignationList] = useState([]);
  const [designationDepartments, setDesignationDepartments] = useState([]);
  const [designationLoading, setDesignationLoading] = useState(false);
  const [designationError, setDesignationError] = useState("");
  const [designationSuccess, setDesignationSuccess] = useState("");
  const [showDesignationForm, setShowDesignationForm] = useState(false);
  const [editingDesignationId, setEditingDesignationId] = useState(null);
  const [designationForm, setDesignationForm] = useState(initialDesignationForm);
  const [designationSaving, setDesignationSaving] = useState(false);
  const [showInactiveDesignations, setShowInactiveDesignations] = useState(false);
  const [designationDepartmentFilter, setDesignationDepartmentFilter] = useState("");

    // Leave Management
  const [leaveRequests, setLeaveRequests] = useState([]);
  const [leaveLoading, setLeaveLoading] = useState(false);
  const [leaveError, setLeaveError] = useState("");
  const [leaveSuccess, setLeaveSuccess] = useState("");
  const [leavePage, setLeavePage] = useState(1);
  const [leaveTotal, setLeaveTotal] = useState(0);
  const [leaveStatusFilter, setLeaveStatusFilter] = useState("Pending");
  const [leaveTypeFilter, setLeaveTypeFilter] = useState("All");
  const [leaveForm, setLeaveForm] = useState({
    leave_type: "Annual",
    start_date: "",
    end_date: "",
    reason: "",
  });
  const [leaveSubmitting, setLeaveSubmitting] = useState(false);
  const [reviewingLeaveId, setReviewingLeaveId] = useState(null);
  const [reviewNote, setReviewNote] = useState("");

  
  // Payroll Management
  const [payrollRecords, setPayrollRecords] = useState([]);
  const [payrollLoading, setPayrollLoading] = useState(false);
  const [payrollError, setPayrollError] = useState("");
  const [payrollSuccess, setPayrollSuccess] = useState("");
  const [payrollPage, setPayrollPage] = useState(1);
  const [payrollTotal, setPayrollTotal] = useState(0);
  const [payrollMonth, setPayrollMonth] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(
      now.getMonth() + 1
    ).padStart(2, "0")}`;
  });
  const [payrollFilterMonth, setPayrollFilterMonth] = useState("");
  const [payrollGenerating, setPayrollGenerating] = useState(false);
  const [finalizingPayrollId, setFinalizingPayrollId] = useState(null);

  const [auditLogs, setAuditLogs] = useState([]);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditError, setAuditError] = useState("");
  const [auditPage, setAuditPage] = useState(1);
  const [auditTotal, setAuditTotal] = useState(0);


  const adminItems = [
    "Dashboard",
    "Employees",
    "Create HR Account",
    "Departments",
    "Designations",
    "Attendance",
    "Leave Management",
    "Payroll",
    "Audit Logs",
    "AI Assistant",
  ];

  const hrItems = [
    "Dashboard",
    "Employees",
    "Departments",
    "Designations",
    "Attendance",
    "Leave Management",
    "Payroll",
    "AI Assistant",
  ];

  const employeeItems = [
    "Dashboard",
    "My Attendance",
    "My Leave",
    "My Payroll",
    "My Profile",
  ];

  const navigation =
    role === "Admin" ? adminItems : role === "HR" ? hrItems : employeeItems;

  // Error handling
  const getErrorMessage = (error, fallback) => {
    const detail = error.response?.data?.detail;

    if (typeof detail === "string") return detail;

    if (Array.isArray(detail)) {
      return detail
        .map((item) => `${item.loc?.at(-1) || "Field"}: ${item.msg}`)
        .join(" ");
    }

    return fallback;
  };

  const getEmployeeId = (employee) =>
    employee?.id || employee?._id || employee?.employee_id || null;

  const getEmployeeName = (employee) =>
    [employee?.first_name, employee?.last_name].filter(Boolean).join(" ") ||
    employee?.employee_code ||
    "—";

  const getEmployeeStatus = (employee) =>
    employee?.employment_status ||
    (typeof employee?.is_active === "boolean"
      ? employee.is_active
        ? "Active"
        : "Inactive"
      : "—");

  const formatDate = (value) => {
    if (!value) return "—";

    const date = new Date(value);

    return Number.isNaN(date.getTime())
      ? value
      : date.toLocaleDateString();
  };

  const getDepartmentName = (departmentId, list = []) => {
    const department = list.find((item) => item.id === departmentId);

    return department
      ? `${department.name} (${department.code})`
      : departmentId || "—";
  };

  const openHRAccountForm = () => {
    if (role !== "Admin") return;

    setShowHRAccountForm(true);
    setHrEmail("");
    setHrInitialPassword("");
    setHrAccountError("");
    setHrAccountSuccess("");

  setShowEmployeeForm(false);
  setViewingEmployee(null);
  setFaceEmployee(null);
  setAccountEmployee(null);
};

const closeHRAccountForm = () => {
  if (hrAccountLoading) return;

  setShowHRAccountForm(false);
  setHrEmail("");
  setHrInitialPassword("");
  setHrAccountError("");
  setHrAccountSuccess("");
};

const handleCreateHRAccount = async (event) => {
  event.preventDefault();

  if (role !== "Admin") {
    setHrAccountError("Only Admin users can create HR accounts.");
    return;
  }

  const email = hrEmail.trim().toLowerCase();

  if (!email) {
    setHrAccountError("Please enter an email address.");
    return;
  }

  if (hrInitialPassword.length < 8) {
    setHrAccountError(
      "The initial password must contain at least 8 characters."
    );
    return;
  }

  if (new TextEncoder().encode(hrInitialPassword).length > 72) {
    setHrAccountError(
      "The password must not exceed 72 UTF-8 bytes."
    );
    return;
  }

  setHrAccountLoading(true);
  setHrAccountError("");
  setHrAccountSuccess("");

  try {
    const response = await api.post("/auth/create-hr-account", {
      email,
      initial_password: hrInitialPassword,
    });

    setHrAccountSuccess(
      `HR account created successfully for ${response.data?.email || email}.`
    );

    setHrEmail("");
    setHrInitialPassword("");
  } catch (error) {
    setHrAccountError(
      getErrorMessage(error, "Unable to create the HR account.")
    );
  } finally {
    setHrAccountLoading(false);
  }
};

  // Stop camera tracks whenever the camera is closed or the component unmounts.
  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }

    setCameraActive(false);
  }, []);

  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  const openFaceEnrollment = (employee) => {
    if (!canManageEmployees) return;

    const employeeId = getEmployeeId(employee);

    if (!employeeId) {
      setEmployeesError("Could not identify this employee. Refresh the list.");
      return;
    }

    stopCamera();
    setFaceEmployee(employee);
    setFaceError("");
    setFaceSuccess("");
    setAccountEmployee(null);
    setAccountError("");
    setAccountSuccess("");
    setInitialPassword("");
    setViewingEmployee(null);
    setShowEmployeeForm(false);
  };

  const closeFaceEnrollment = () => {
    if (faceLoading) return;

    stopCamera();
    setFaceEmployee(null);
    setFaceError("");
    setFaceSuccess("");
  };

  const startCamera = async () => {
    setFaceError("");
    setFaceSuccess("");

    if (!navigator.mediaDevices?.getUserMedia) {
      setFaceError(
        "Camera access is unavailable. Use a supported browser and HTTPS or localhost."
      );
      return;
    }

    try {
      stopCamera();

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: {
          facingMode: "user",
          width: { ideal: 640 },
          height: { ideal: 480 },
        },
      });

      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }

      setCameraActive(true);
    } catch (error) {
      stopCamera();

      if (error.name === "NotAllowedError") {
        setFaceError(
          "Camera permission was denied. Allow camera access in your browser settings and try again."
        );
      } else if (
        error.name === "NotFoundError" ||
        error.name === "DevicesNotFoundError"
      ) {
        setFaceError("No camera was found on this device.");
      } else {
        setFaceError(
          error.message || "Unable to start the camera. Please try again."
        );
      }
    }
  };

  const handleEnrollFace = async () => {
    if (!canManageEmployees || !faceEmployee) {
      setFaceError("Employee information is missing.");
      return;
    }

    const employeeId = getEmployeeId(faceEmployee);

    if (!employeeId) {
      setFaceError("Could not identify this employee.");
      return;
    }

    if (!videoRef.current || !cameraActive) {
      setFaceError("Start the camera before capturing the employee's face.");
      return;
    }

    setFaceLoading(true);
    setFaceError("");
    setFaceSuccess("");

    try {
      const captured = await captureVideoFrame(videoRef.current);

      // Support helpers that return either a base64 string or an object.
      const imageBase64 =
        typeof captured === "string"
          ? captured
          : captured?.image_base64 || captured?.base64 || captured?.data;

      if (!imageBase64 || typeof imageBase64 !== "string") {
        throw new Error(
          "The camera image could not be captured. Please try again."
        );
      }

      const response = await api.post(
        `/face/enroll/${encodeURIComponent(employeeId)}`,
        { image_base64: imageBase64 }
      );

      setFaceEnrolledIds((previous) => {
        const next = new Set(previous);
        next.add(String(employeeId));
        return next;
      });

      setFaceSuccess(
        response.data?.message || "Face enrolled successfully."
      );

      stopCamera();
    } catch (error) {
      setFaceError(
        getErrorMessage(error, "Unable to enroll this employee's face.")
      );
    } finally {
      setFaceLoading(false);
    }
  };

  const continueToCreateLogin = () => {
    if (!faceEmployee) return;

    const employee = faceEmployee;

    stopCamera();
    setFaceEmployee(null);
    setFaceError("");
    setFaceSuccess("");
    openAccountForm(employee);
  };

  // Close organization-management forms if the role changes.
  useEffect(() => {
    if (!canManageOrganization) {
      setShowDepartmentForm(false);
      setShowDesignationForm(false);
      setEditingDepartmentId(null);
      setEditingDesignationId(null);
    }
  }, [canManageOrganization]);

  // Dashboard summary
  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      if (!["Admin", "HR", "Employee"].includes(role)) {
        setSummary(null);
        setSummaryError("");
        setSummaryLoading(false);
        return;
      }

      setSummaryLoading(true);
      setSummaryError("");

      try {
        const endpoint =
          role === "Admin" || role === "HR"
            ? "/dashboards/admin-summary"
            : "/dashboards/employee-summary";

        const response = await api.get(endpoint);

        if (!cancelled) setSummary(response.data);
      } catch (error) {
        if (!cancelled) {
          setSummaryError(
            getErrorMessage(error, "Unable to load dashboard statistics.")
          );
        }
      } finally {
        if (!cancelled) setSummaryLoading(false);
      }
    };

    load();

    return () => {
      cancelled = true;
    };
  }, [role, activePage]);

  // Employee list
  const fetchEmployees = async (page = employeePage) => {
    setEmployeesLoading(true);
    setEmployeesError("");

    try {
      const response = await api.get("/employees", {
        params: { page, page_size: 20 },
      });

      const data = response.data;
      const items = Array.isArray(data?.items)
        ? data.items
        : Array.isArray(data)
          ? data
          : [];

      setEmployees(items);
      setEmployeeTotal(data?.total ?? items.length);
    } catch (error) {
      setEmployeesError(getErrorMessage(error, "Unable to load employees."));
    } finally {
      setEmployeesLoading(false);
    }
  };

  useEffect(() => {
    if (activePage !== "Employees") return;

    let cancelled = false;

    const load = async () => {
      setEmployeesLoading(true);
      setEmployeesError("");

      try {
        const response = await api.get("/employees", {
          params: { page: employeePage, page_size: 20 },
        });

        if (cancelled) return;

        const data = response.data;
        const items = Array.isArray(data?.items)
          ? data.items
          : Array.isArray(data)
            ? data
            : [];

        setEmployees(items);
        setEmployeeTotal(data?.total ?? items.length);
      } catch (error) {
        if (!cancelled) {
          setEmployeesError(
            getErrorMessage(error, "Unable to load employees.")
          );
        }
      } finally {
        if (!cancelled) setEmployeesLoading(false);
      }
    };

    load();

    return () => {
      cancelled = true;
    };
  }, [activePage, employeePage]);

  // Active departments for employee form
  useEffect(() => {
    if (!showEmployeeForm) return;

    let cancelled = false;

    const load = async () => {
      setOptionsLoading(true);

      try {
        const response = await api.get("/departments", {
          params: { page: 1, page_size: 100 },
        });

        if (!cancelled) {
          setDepartments(
            (response.data?.items ?? []).filter((item) => item.is_active)
          );
        }
      } catch (error) {
        if (!cancelled) {
          setFormError(getErrorMessage(error, "Could not load departments."));
        }
      } finally {
        if (!cancelled) setOptionsLoading(false);
      }
    };

    load();

    return () => {
      cancelled = true;
    };
  }, [showEmployeeForm]);

  // Active designations for the selected employee department
  useEffect(() => {
    const departmentId = employeeForm.department_id;

    setDesignations([]);

    if (!showEmployeeForm || !departmentId) return;

    let cancelled = false;

    const load = async () => {
      try {
        const response = await api.get("/designations", {
          params: {
            department_id: departmentId,
            page: 1,
            page_size: 100,
          },
        });

        if (!cancelled) {
          setDesignations(
            (response.data?.items ?? []).filter(
              (item) =>
                item.is_active && item.department_id === departmentId
            )
          );
        }
      } catch (error) {
        if (!cancelled) {
          setFormError(
            getErrorMessage(error, "Could not load designations.")
          );
        }
      }
    };

    load();

    return () => {
      cancelled = true;
    };
  }, [showEmployeeForm, employeeForm.department_id]);

  // Department management list
  useEffect(() => {
    if (activePage !== "Departments") return;

    let cancelled = false;

    const load = async () => {
      setDepartmentsLoading(true);
      setDepartmentsError("");

      try {
        const response = await api.get("/departments", {
          params: {
            page: 1,
            page_size: 100,
            include_inactive: showInactiveDepartments,
          },
        });

        if (!cancelled) {
          setDepartmentsList(response.data?.items ?? []);
        }
      } catch (error) {
        if (!cancelled) {
          setDepartmentsError(
            getErrorMessage(error, "Unable to load departments.")
          );
        }
      } finally {
        if (!cancelled) setDepartmentsLoading(false);
      }
    };

    load();

    return () => {
      cancelled = true;
    };
  }, [activePage, showInactiveDepartments]);

  // Load designations and departments for designation management
  useEffect(() => {
    if (activePage !== "Designations") return;

    let cancelled = false;

    const load = async () => {
      setDesignationLoading(true);
      setDesignationError("");

      try {
        const [designationResponse, departmentResponse] = await Promise.all([
          api.get("/designations", {
            params: {
              page: 1,
              page_size: 100,
              include_inactive: showInactiveDesignations,
              ...(designationDepartmentFilter
                ? { department_id: designationDepartmentFilter }
                : {}),
            },
          }),
          api.get("/departments", {
            params: {
              page: 1,
              page_size: 100,
              include_inactive: true,
            },
          }),
        ]);

        if (!cancelled) {
          setDesignationList(designationResponse.data?.items ?? []);
          setDesignationDepartments(departmentResponse.data?.items ?? []);
        }
      } catch (error) {
        if (!cancelled) {
          setDesignationError(
            getErrorMessage(error, "Unable to load designations.")
          );
        }
      } finally {
        if (!cancelled) setDesignationLoading(false);
      }
    };

    load();

    return () => {
      cancelled = true;
    };
  }, [
    activePage,
    showInactiveDesignations,
    designationDepartmentFilter,
  ]);

  const refreshDesignations = async () => {
    setDesignationLoading(true);
    setDesignationError("");

    try {
      const [designationResponse, departmentResponse] = await Promise.all([
        api.get("/designations", {
          params: {
            page: 1,
            page_size: 100,
            include_inactive: showInactiveDesignations,
            ...(designationDepartmentFilter
              ? { department_id: designationDepartmentFilter }
              : {}),
          },
        }),
        api.get("/departments", {
          params: {
            page: 1,
            page_size: 100,
            include_inactive: true,
          },
        }),
      ]);

      setDesignationList(designationResponse.data?.items ?? []);
      setDesignationDepartments(departmentResponse.data?.items ?? []);
    } catch (error) {
      setDesignationError(
        getErrorMessage(error, "Unable to refresh designations.")
      );
    } finally {
      setDesignationLoading(false);
    }
  };

  // Employee login account creation
  const openAccountForm = (employee) => {
    if (!canManageEmployees) return;

    setAccountEmployee(employee);
    setInitialPassword("");
    setAccountError("");
    setAccountSuccess("");
    setShowEmployeeForm(false);
    setViewingEmployee(null);
    setViewError("");
  };

  const closeAccountForm = () => {
    if (accountLoading) return;

    setAccountEmployee(null);
    setInitialPassword("");
    setAccountError("");
    setAccountSuccess("");
  };

  const handleCreateEmployeeAccount = async (event) => {
    event.preventDefault();

    if (!canManageEmployees || !accountEmployee) {
      setAccountError("Employee information is missing.");
      return;
    }

    const employeeId = getEmployeeId(accountEmployee);

    if (!employeeId) {
      setAccountError(
        "Could not identify this employee. Refresh the employee list and try again."
      );
      return;
    }

    if (!accountEmployee.email) {
      setAccountError(
        "This employee has no email address. Update the employee record first."
      );
      return;
    }

    if (getEmployeeStatus(accountEmployee) !== "Active") {
      setAccountError("Only active employees can receive login accounts.");
      return;
    }

    if (!faceEnrolledIds.has(String(employeeId))) {
      setAccountError(
        "Enroll this employee's face before creating a login account."
      );
      return;
    }

    if (initialPassword.length < 8) {
      setAccountError(
        "The initial password must contain at least 8 characters."
      );
      return;
    }

    setAccountLoading(true);
    setAccountError("");
    setAccountSuccess("");

    try {
      const response = await api.post("/auth/create-employee-account", {
        employee_id: employeeId,
        initial_password: initialPassword,
      });

      setAccountSuccess(
        response.data?.message ||
          "Employee login account created successfully."
      );

      setInitialPassword("");
    } catch (error) {
      setAccountError(
        getErrorMessage(
          error,
          "Unable to create the employee login account."
        )
      );
    } finally {
      setAccountLoading(false);
    }
  };

  // Employee form handlers
  const openEmployeeForm = () => {
    if (!canManageEmployees) return;

    setEditingEmployeeId(null);
    setEmployeeForm(initialEmployeeForm);
    setFormError("");
    setFormSuccess("");
    setViewingEmployee(null);
    setViewError("");
    setAccountEmployee(null);
    setFaceEmployee(null);
    setShowEmployeeForm(true);
  };

  const openEditEmployee = async (employeeId) => {
    if (!canManageEmployees || !employeeId) return;

    setFormError("");
    setFormSuccess("");
    setViewError("");
    setViewingEmployee(null);
    setAccountEmployee(null);
    setFaceEmployee(null);
    setEditingEmployeeId(employeeId);
    setEmployeeForm(initialEmployeeForm);
    setDesignations([]);
    setShowEmployeeForm(true);
    setFormLoading(true);

    try {
      const response = await api.get(`/employees/${employeeId}`);
      const employee = response.data;

      setEmployeeForm({
        employee_code: employee.employee_code ?? "",
        first_name: employee.first_name ?? "",
        last_name: employee.last_name ?? "",
        email: employee.email ?? "",
        phone: employee.phone ?? "",
        department_id: employee.department_id ?? "",
        designation_id: employee.designation_id ?? "",
        manager_id: employee.manager_id ?? "",
        joining_date: employee.joining_date
          ? String(employee.joining_date).slice(0, 10)
          : "",
        employment_status: employee.employment_status ?? "Active",
        basic_salary: String(employee.basic_salary ?? ""),
      });
    } catch (error) {
      setFormError(
        getErrorMessage(
          error,
          "Unable to load employee details for editing."
        )
      );
    } finally {
      setFormLoading(false);
    }
  };

  const openViewEmployee = async (employeeId) => {
    if (!employeeId) {
      setViewError("Could not identify this employee.");
      return;
    }

    stopCamera();
    setFaceEmployee(null);
    setShowEmployeeForm(false);
    setEditingEmployeeId(null);
    setAccountEmployee(null);
    setViewLoading(true);
    setViewError("");
    setViewingEmployee(null);

    try {
      const response = await api.get(`/employees/${employeeId}`);
      setViewingEmployee(response.data);
    } catch (error) {
      setViewError(
        getErrorMessage(error, "Unable to load employee details.")
      );
    } finally {
      setViewLoading(false);
    }
  };

  const closeEmployeeDetails = () => {
    setViewingEmployee(null);
    setViewError("");
  };

  const closeEmployeeForm = () => {
    if (formLoading) return;

    setShowEmployeeForm(false);
    setEditingEmployeeId(null);
    setEmployeeForm(initialEmployeeForm);
    setFormError("");
    setFormSuccess("");
    setDesignations([]);
  };

  const handleEmployeeFieldChange = (event) => {
    const { name, value } = event.target;

    setFormError("");
    setFormSuccess("");

    setEmployeeForm((previous) => {
      const next = { ...previous, [name]: value };

      if (name === "department_id") {
        next.designation_id = "";
      }

      return next;
    });
  };

  const handleSaveEmployee = async (event) => {
    event.preventDefault();

    if (!canManageEmployees) return;

    setFormError("");
    setFormSuccess("");

    if (!employeeForm.department_id || !employeeForm.designation_id) {
      setFormError("Please select both a department and a designation.");
      return;
    }

    if (!employeeForm.joining_date) {
      setFormError("Please select the employee's joining date.");
      return;
    }

    const salary = Number(employeeForm.basic_salary);

    if (!Number.isFinite(salary) || salary <= 0) {
      setFormError("Basic salary must be a number greater than zero.");
      return;
    }

    const payload = {
      first_name: employeeForm.first_name.trim(),
      last_name: employeeForm.last_name.trim(),
      email: employeeForm.email.trim().toLowerCase(),
      phone: employeeForm.phone.trim() || null,
      department_id: employeeForm.department_id,
      designation_id: employeeForm.designation_id,
      manager_id: employeeForm.manager_id || null,
      joining_date: employeeForm.joining_date,
      employment_status: employeeForm.employment_status,
      basic_salary: salary,
    };

    setFormLoading(true);

    try {
      if (editingEmployeeId) {
        await api.patch(`/employees/${editingEmployeeId}`, payload);
        setFormSuccess("Employee updated successfully.");
      } else {
        await api.post("/employees", {
          employee_code: employeeForm.employee_code.trim().toUpperCase(),
          ...payload,
        });

        setFormSuccess("Employee created successfully.");
      }

      const response = await api.get("/employees", {
        params: { page: 1, page_size: 20 },
      });

      const data = response.data;
      const items = Array.isArray(data?.items)
        ? data.items
        : Array.isArray(data)
          ? data
          : [];

      setEmployees(items);
      setEmployeeTotal(data?.total ?? items.length);
      setEmployeePage(1);
      setShowEmployeeForm(false);
      setEditingEmployeeId(null);
      setEmployeeForm(initialEmployeeForm);
      setDesignations([]);
      setFormError("");
    } catch (error) {
      setFormError(
        getErrorMessage(
          error,
          editingEmployeeId
            ? "Unable to update employee."
            : "Unable to create employee."
        )
      );
    } finally {
      setFormLoading(false);
    }
  };

  // Department handlers: Admin only
  const openDepartmentForm = (department = null) => {
    if (!canManageOrganization) return;

    setEditingDepartmentId(department?.id ?? null);

    setDepartmentForm({
      name: department?.name ?? "",
      code: department?.code ?? "",
      description: department?.description ?? "",
    });

    setDepartmentsError("");
    setDepartmentSuccess("");
    setShowDepartmentForm(true);
  };

  const closeDepartmentForm = () => {
    if (departmentSaving) return;

    setShowDepartmentForm(false);
    setEditingDepartmentId(null);
    setDepartmentForm(initialDepartmentForm);
    setDepartmentsError("");
  };

  const handleDepartmentFieldChange = (event) => {
    if (!canManageOrganization) return;

    const { name, value } = event.target;

    setDepartmentForm((previous) => ({
      ...previous,
      [name]: value,
    }));
  };

  const handleSaveDepartment = async (event) => {
    event.preventDefault();

    if (!canManageOrganization) return;

    setDepartmentsError("");
    setDepartmentSuccess("");

    const payload = {
      name: departmentForm.name.trim(),
      code: departmentForm.code.trim().toUpperCase(),
      description: departmentForm.description.trim() || null,
    };

    if (!payload.name || !payload.code) {
      setDepartmentsError("Department name and code are required.");
      return;
    }

    setDepartmentSaving(true);

    try {
      if (editingDepartmentId) {
        await api.patch(`/departments/${editingDepartmentId}`, payload);
        setDepartmentSuccess("Department updated successfully.");
      } else {
        await api.post("/departments", payload);
        setDepartmentSuccess("Department created successfully.");
      }

      setShowDepartmentForm(false);
      setEditingDepartmentId(null);
      setDepartmentForm(initialDepartmentForm);

      const response = await api.get("/departments", {
        params: {
          page: 1,
          page_size: 100,
          include_inactive: showInactiveDepartments,
        },
      });

      setDepartmentsList(response.data?.items ?? []);
    } catch (error) {
      setDepartmentsError(
        getErrorMessage(
          error,
          "Unable to save department. Please check the entered information."
        )
      );
    } finally {
      setDepartmentSaving(false);
    }
  };

  const handleDepartmentStatus = async (department) => {
    if (!canManageOrganization) return;

    setDepartmentsError("");
    setDepartmentSuccess("");

    try {
      await api.patch(`/departments/${department.id}/status`, {
        is_active: !department.is_active,
      });

      setDepartmentSuccess(
        `${department.name} ${
          department.is_active ? "deactivated" : "activated"
        } successfully.`
      );

      const response = await api.get("/departments", {
        params: {
          page: 1,
          page_size: 100,
          include_inactive: showInactiveDepartments,
        },
      });

      setDepartmentsList(response.data?.items ?? []);
    } catch (error) {
      setDepartmentsError(
        getErrorMessage(error, "Unable to update department status.")
      );
    }
  };

  async function fetchDepartmentList() {
    setDepartmentsLoading(true);
    setDepartmentsError("");

    try {
      const response = await api.get("/departments", {
        params: {
          page: 1,
          page_size: 100,
          include_inactive: showInactiveDepartments,
        },
      });

      setDepartmentsList(response.data?.items ?? []);
    } catch (error) {
      setDepartmentsError(
        getErrorMessage(error, "Unable to load departments.")
      );
    } finally {
      setDepartmentsLoading(false);
    }
  }

  // Designation handlers: Admin only
  const openDesignationForm = (designation = null) => {
    if (!canManageOrganization) return;

    setEditingDesignationId(designation?.id ?? null);

    setDesignationForm({
      name: designation?.name ?? "",
      code: designation?.code ?? "",
      department_id: designation?.department_id ?? "",
      description: designation?.description ?? "",
    });

    setDesignationError("");
    setDesignationSuccess("");
    setShowDesignationForm(true);
  };

  const closeDesignationForm = () => {
    if (designationSaving) return;

    setShowDesignationForm(false);
    setEditingDesignationId(null);
    setDesignationForm(initialDesignationForm);
    setDesignationError("");
  };

  const handleDesignationFieldChange = (event) => {
    if (!canManageOrganization) return;

    const { name, value } = event.target;

    setDesignationForm((previous) => ({
      ...previous,
      [name]: value,
    }));
  };

  const handleSaveDesignation = async (event) => {
    event.preventDefault();

    if (!canManageOrganization) return;

    setDesignationError("");
    setDesignationSuccess("");

    const payload = {
      name: designationForm.name.trim(),
      code: designationForm.code.trim().toUpperCase(),
      description: designationForm.description.trim() || null,
    };

    if (!payload.name || !payload.code) {
      setDesignationError("Designation name and code are required.");
      return;
    }

    if (!editingDesignationId && !designationForm.department_id) {
      setDesignationError("Please select a department.");
      return;
    }

    setDesignationSaving(true);

    try {
      if (editingDesignationId) {
        await api.patch(`/designations/${editingDesignationId}`, payload);
        setDesignationSuccess("Designation updated successfully.");
      } else {
        await api.post("/designations", {
          ...payload,
          department_id: designationForm.department_id,
        });

        setDesignationSuccess("Designation created successfully.");
      }

      setShowDesignationForm(false);
      setEditingDesignationId(null);
      setDesignationForm(initialDesignationForm);

      await refreshDesignations();
    } catch (error) {
      setDesignationError(
        getErrorMessage(
          error,
          "Unable to save designation. Check the name, code, and department."
        )
      );
    } finally {
      setDesignationSaving(false);
    }
  };

  const handleDesignationStatus = async (designation) => {
    if (!canManageOrganization) return;

    setDesignationError("");
    setDesignationSuccess("");

    try {
      await api.patch(`/designations/${designation.id}/status`, {
        is_active: !designation.is_active,
      });

      setDesignationSuccess(
        `${designation.name} ${
          designation.is_active ? "deactivated" : "activated"
        } successfully.`
      );

      await refreshDesignations();
    } catch (error) {
      setDesignationError(
        getErrorMessage(error, "Unable to update designation status.")
      );
    }
  };

    // Leave Management API
  const fetchLeaveRequests = useCallback(async () => {
    if (activePage !== "Leave Management" && activePage !== "My Leave") {
      return;
    }

    setLeaveLoading(true);
    setLeaveError("");

    try {
      const isEmployee = role === "Employee";

      const response = await api.get(
        isEmployee ? "/leave/my" : "/leave",
        {
          params: {
            page: leavePage,
            page_size: 20,
            ...(!isEmployee && leaveStatusFilter !== "All"
              ? { status: leaveStatusFilter }
              : {}),
          },
        }
      );

      setLeaveRequests(response.data?.items ?? []);
      setLeaveTotal(response.data?.total ?? 0);
    } catch (error) {
      setLeaveError(
        getErrorMessage(error, "Unable to load leave requests.")
      );
    } finally {
      setLeaveLoading(false);
    }
  }, [activePage, role, leavePage, leaveStatusFilter]);

  useEffect(() => {
    if (activePage !== "Leave Management" && activePage !== "My Leave") {
      return;
    }

    fetchLeaveRequests();
  }, [activePage, fetchLeaveRequests]);

  
  useEffect(() => {
    if (activePage !== "Payroll" && activePage !== "My Payroll") {
      return;
    }

    fetchPayrollRecords(payrollPage);

    // The effect runs when the selected page, page number, or month filter changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activePage, payrollPage, payrollFilterMonth]);


  const handleApplyForLeave = async (event) => {
    event.preventDefault();

    if (role !== "Employee") return;

    setLeaveError("");
    setLeaveSuccess("");

    if (leaveForm.end_date < leaveForm.start_date) {
      setLeaveError("End date cannot be before start date.");
      return;
    }

    setLeaveSubmitting(true);

    try {
      await api.post("/leave", {
        leave_type: leaveForm.leave_type,
        start_date: leaveForm.start_date,
        end_date: leaveForm.end_date,
        reason: leaveForm.reason.trim(),
      });

      setLeaveSuccess("Your leave request was submitted successfully.");
      setLeaveForm({
        leave_type: "Annual",
        start_date: "",
        end_date: "",
        reason: "",
      });

      setLeavePage(1);

      const response = await api.get("/leave/my", {
        params: { page: 1, page_size: 20 },
      });

      setLeaveRequests(response.data?.items ?? []);
      setLeaveTotal(response.data?.total ?? 0);
    } catch (error) {
      setLeaveError(
        getErrorMessage(error, "Unable to submit your leave request.")
      );
    } finally {
      setLeaveSubmitting(false);
    }
  };

  const handleCancelLeave = async (leaveId) => {
    if (role !== "Employee" || !leaveId) return;

    const confirmed = window.confirm(
      "Are you sure you want to cancel this pending leave request?"
    );

    if (!confirmed) return;

    setLeaveError("");
    setLeaveSuccess("");

    try {
      await api.patch(`/leave/${leaveId}/cancel`);

      setLeaveSuccess("Leave request cancelled successfully.");
      await fetchLeaveRequests();
    } catch (error) {
      setLeaveError(
        getErrorMessage(error, "Unable to cancel the leave request.")
      );
    }
  };

  const handleReviewLeave = async (leaveId, decision) => {
    if (!canManageEmployees || !leaveId) return;

    setLeaveError("");
    setLeaveSuccess("");
    setReviewingLeaveId(leaveId);

    try {
      await api.patch(`/leave/${leaveId}/review`, {
        status: decision,
        review_note: reviewNote.trim() || null,
      });

      setLeaveSuccess(`Leave request ${decision.toLowerCase()} successfully.`);
      setReviewNote("");
      await fetchLeaveRequests();
    } catch (error) {
      setLeaveError(
        getErrorMessage(error, "Unable to review the leave request.")
      );
    } finally {
      setReviewingLeaveId(null);
    }
  };

  
  // Fetch payroll records for Admin/HR or personal payroll for Employee.
  const fetchPayrollRecords = async (page = payrollPage) => {
    setPayrollLoading(true);
    setPayrollError("");

    try {
      const isEmployee = role === "Employee";

      const response = await api.get(
        isEmployee ? "/payroll/my" : "/payroll",
        {
          params: {
            page,
            page_size: 20,
            ...(!isEmployee && payrollFilterMonth
              ? { payroll_month: payrollFilterMonth }
              : {}),
          },
        }
      );

      setPayrollRecords(response.data?.items ?? []);
      setPayrollTotal(response.data?.total ?? 0);
    } catch (error) {
      setPayrollError(
        getErrorMessage(error, "Unable to load payroll records.")
      );
    } finally {
      setPayrollLoading(false);
    }
  };

  // Audit Logs API — Admin only
const fetchAuditLogs = useCallback(async (page = auditPage) => {
  if (role !== "Admin" || activePage !== "Audit Logs") {
    return;
  }

  setAuditLoading(true);
  setAuditError("");

  try {
    const response = await api.get("/audit-logs", {
      params: {
        page,
        page_size: 20,
      },
    });

    setAuditLogs(response.data?.items ?? []);
    setAuditTotal(response.data?.total ?? 0);
  } catch (error) {
    setAuditError(
      getErrorMessage(error, "Unable to load audit logs.")
    );
  } finally {
    setAuditLoading(false);
  }
}, [activePage, role, auditPage]);

useEffect(() => {
  if (activePage === "Audit Logs" && role === "Admin") {
    fetchAuditLogs(auditPage);
  }
}, [activePage, role, auditPage, fetchAuditLogs]);

  // Generate payroll — Admin only.
  const handleGeneratePayroll = async (event) => {
    event.preventDefault();

    if (role !== "Admin") {
      setPayrollError("Only Admin users can generate payroll.");
      return;
    }

    if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(payrollMonth)) {
      setPayrollError("Select a valid payroll month.");
      return;
    }

    setPayrollGenerating(true);
    setPayrollError("");
    setPayrollSuccess("");

    try {
      const response = await api.post("/payroll/generate", {
        payroll_month: payrollMonth,
      });

      setPayrollRecords(response.data?.items ?? []);
      setPayrollTotal(response.data?.total ?? 0);
      setPayrollPage(1);

      setPayrollSuccess(
        `Payroll generated successfully for ${payrollMonth}.`
      );

      await fetchPayrollRecords(1);
    } catch (error) {
      setPayrollError(
        getErrorMessage(
          error,
          "Unable to generate payroll. Check the month and existing payroll records."
        )
      );
    } finally {
      setPayrollGenerating(false);
    }
  };

  // Finalize payroll — Admin only.
  const handleFinalizePayroll = async (payrollId) => {
    if (role !== "Admin") {
      setPayrollError("Only Admin users can finalize payroll.");
      return;
    }

    const confirmed = window.confirm(
      "Finalize this payroll record? Finalized payroll cannot be edited through this workflow."
    );

    if (!confirmed) return;

    setFinalizingPayrollId(payrollId);
    setPayrollError("");
    setPayrollSuccess("");

    try {
      await api.patch(`/payroll/${payrollId}/finalize`);

      setPayrollSuccess("Payroll finalized successfully.");
      await fetchPayrollRecords(payrollPage);
    } catch (error) {
      setPayrollError(
        getErrorMessage(error, "Unable to finalize payroll.")
      );
    } finally {
      setFinalizingPayrollId(null);
    }
  };


  // Dashboard page
  const renderDashboard = () => (
    <>
      <div className="welcome-banner">
        <div>
          <p className="welcome-eyebrow">HCM LITE WORKSPACE</p>
          <h2>Welcome back!</h2>
          <p>Manage your work and access your HR tools from one place.</p>
        </div>
        <div className="welcome-decoration">H</div>
      </div>

      <div className="section-heading">
        <div>
          <h2>Overview</h2>
          <p>Your workspace at a glance.</p>
        </div>
        <span className="role-badge">{role}</span>
      </div>

      <section className="overview-grid">
        {summaryLoading && <p>Loading dashboard statistics...</p>}
        {summaryError && <p className="error-message">{summaryError}</p>}

        {!summaryLoading && summary && (role === "Admin" || role === "HR") && (
          <>
            {[
              ["Total Employees", summary.employees?.total ?? 0],
              ["Active Employees", summary.employees?.active ?? 0],
              ["Attendance Today", summary.attendance?.records_today ?? 0],
              ["Present or Late", summary.attendance?.present_or_late ?? 0],
              ["Pending Leave Requests", summary.leave_requests?.pending ?? 0],
              ["Draft Payrolls", summary.payroll?.draft ?? 0],
              ["Finalized Payrolls", summary.payroll?.finalized ?? 0],
              ["Late Arrivals", summary.attendance?.late ?? 0],
            ].map(([label, value]) => (
              <div className="overview-card" key={label}>
                <span>{label}</span>
                <h2>{value}</h2>
              </div>
            ))}
          </>
        )}

        {!summaryLoading && summary && role === "Employee" && (
          <>
            {[
              ["Pending Leave Requests", summary.leave_requests?.pending ?? 0],
              ["Approved Leave Requests", summary.leave_requests?.approved ?? 0],
              ["Rejected Leave Requests", summary.leave_requests?.rejected ?? 0],
              ["Cancelled Leave Requests", summary.leave_requests?.cancelled ?? 0],
              ["Today's Attendance", summary.attendance_today?.status ?? "No record"],
              ["Latest Payroll", summary.latest_payroll ? "Available" : "No payroll yet"],
            ].map(([label, value]) => (
              <div className="overview-card" key={label}>
                <span>{label}</span>
                <h2>{value}</h2>
              </div>
            ))}
          </>
        )}

        {!summaryLoading && !summary && !summaryError && (
          <p>Dashboard statistics are not available for this role yet.</p>
        )}
      </section>

      <section className="quick-access">
        <h2>Quick access</h2>
        <p>Available workspace sections depend on your account role.</p>
        <div className="quick-access-grid">
          {navigation.slice(1, 5).map((item) => (
            <button
              className="quick-access-item"
              key={item}
              type="button"
              onClick={() => setActivePage(item)}
            >
              <span className="quick-access-icon">↗</span>
              <span>{item}</span>
            </button>
          ))}
        </div>
      </section>
    </>
  );

  // Employee create/edit form
  const renderEmployeeForm = () => (
    <section className="employee-form-card">
      <div className="section-heading employee-form-heading">
        <div>
          <h2>{editingEmployeeId ? "Edit Employee" : "Add New Employee"}</h2>
          <p>
            {editingEmployeeId
              ? "Update the employee details below."
              : "Fields marked * are required."}
          </p>
        </div>
        <button
          className="secondary-button"
          type="button"
          onClick={closeEmployeeForm}
          disabled={formLoading}
        >
          Cancel
        </button>
      </div>

      {formError && (
        <div className="form-alert form-alert-error" role="alert">
          {formError}
        </div>
      )}
      {formSuccess && (
        <div className="form-alert form-alert-success" role="status">
          {formSuccess}
        </div>
      )}
      {optionsLoading && <p>Loading departments...</p>}
      {formLoading && editingEmployeeId && <p>Loading employee details...</p>}

      <form onSubmit={handleSaveEmployee}>
        <div className="employee-form-grid">
          <label className="form-field">
            Employee Code *
            <input
              name="employee_code"
              value={employeeForm.employee_code}
              onChange={handleEmployeeFieldChange}
              required
              maxLength={120}
              placeholder="e.g. EMP001"
              autoComplete="off"
              readOnly={Boolean(editingEmployeeId)}
            />
          </label>

          <label className="form-field">
            Joining Date *
            <input
              name="joining_date"
              type="date"
              value={employeeForm.joining_date}
              onChange={handleEmployeeFieldChange}
              required
            />
          </label>

          <label className="form-field">
            First Name *
            <input
              name="first_name"
              value={employeeForm.first_name}
              onChange={handleEmployeeFieldChange}
              required
              maxLength={120}
              autoComplete="given-name"
            />
          </label>

          <label className="form-field">
            Last Name *
            <input
              name="last_name"
              value={employeeForm.last_name}
              onChange={handleEmployeeFieldChange}
              required
              maxLength={120}
              autoComplete="family-name"
            />
          </label>

          <label className="form-field">
            Email *
            <input
              name="email"
              type="email"
              value={employeeForm.email}
              onChange={handleEmployeeFieldChange}
              required
              autoComplete="email"
              maxLength={254}
            />
          </label>

          <label className="form-field">
            Phone
            <input
              name="phone"
              type="tel"
              value={employeeForm.phone}
              onChange={handleEmployeeFieldChange}
              maxLength={30}
              autoComplete="tel"
              placeholder="Optional"
            />
          </label>

          <label className="form-field">
            Department *
            <select
              name="department_id"
              value={employeeForm.department_id}
              onChange={handleEmployeeFieldChange}
              required
              disabled={optionsLoading || departments.length === 0}
            >
              <option value="">Select department</option>
              {departments.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name} ({item.code})
                </option>
              ))}
            </select>
          </label>

          <label className="form-field">
            Designation *
            <select
              name="designation_id"
              value={employeeForm.designation_id}
              onChange={handleEmployeeFieldChange}
              required
              disabled={!employeeForm.department_id || designations.length === 0}
            >
              <option value="">Select designation</option>
              {designations.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name} ({item.code})
                </option>
              ))}
            </select>
            {employeeForm.department_id && designations.length === 0 && (
              <small className="field-hint">
                No active designations found for this department.
              </small>
            )}
          </label>

          <label className="form-field">
            Manager
            <select
              name="manager_id"
              value={employeeForm.manager_id}
              onChange={handleEmployeeFieldChange}
            >
              <option value="">No manager selected</option>
              {employees
                .filter(
                  (item) =>
                    getEmployeeId(item) &&
                    item.employment_status === "Active"
                )
                .map((item) => (
                  <option key={getEmployeeId(item)} value={getEmployeeId(item)}>
                    {getEmployeeName(item)} ({item.employee_code})
                  </option>
                ))}
            </select>
            <small className="field-hint">
              Only active employees on the currently loaded page are shown.
            </small>
          </label>

          <label className="form-field">
            Employment Status
            <select
              name="employment_status"
              value={employeeForm.employment_status}
              onChange={handleEmployeeFieldChange}
            >
              <option value="Active">Active</option>
              <option value="OnLeave">On Leave</option>
              <option value="Resigned">Resigned</option>
              <option value="Terminated">Terminated</option>
            </select>
          </label>

          <label className="form-field">
            Basic Salary *
            <input
              name="basic_salary"
              type="number"
              value={employeeForm.basic_salary}
              onChange={handleEmployeeFieldChange}
              required
              min="0.01"
              max="100000000"
              step="0.01"
              placeholder="Enter basic salary"
            />
          </label>
        </div>

        <div className="employee-form-actions">
          <button
            className="secondary-button"
            type="button"
            onClick={closeEmployeeForm}
            disabled={formLoading}
          >
            Cancel
          </button>
          <button
            className="primary-button"
            type="submit"
            disabled={formLoading || optionsLoading}
          >
            {formLoading
              ? "Saving Employee..."
              : editingEmployeeId
                ? "Save Changes"
                : "Save Employee"}
          </button>
        </div>
      </form>
    </section>
  );

  // Face enrollment screen
  const renderFaceEnrollment = () => (
    <section className="employee-form-card">
      <div className="section-heading employee-form-heading">
        <div>
          <h2>Employee Face Enrollment</h2>
          <p>
            Capture a clear image of the employee's face before creating a login.
          </p>
        </div>

        <button
          className="secondary-button"
          type="button"
          onClick={closeFaceEnrollment}
          disabled={faceLoading}
        >
          Back to Employees
        </button>
      </div>

      {faceEmployee && (
        <div className="employee-form-grid">
          <div className="form-field">
            <span>Employee</span>
            <strong>{getEmployeeName(faceEmployee)}</strong>
          </div>
          <div className="form-field">
            <span>Employee Code</span>
            <strong>{faceEmployee.employee_code || "—"}</strong>
          </div>
          <div className="form-field">
            <span>Email</span>
            <strong>{faceEmployee.email || "—"}</strong>
          </div>
        </div>
      )}

      {faceError && (
        <div className="form-alert form-alert-error" role="alert">
          {faceError}
        </div>
      )}

      {faceSuccess && (
        <div className="form-alert form-alert-success" role="status">
          {faceSuccess}
        </div>
      )}

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "16px",
          marginTop: "24px",
        }}
      >
        <video
          ref={videoRef}
          autoPlay
          muted
          playsInline
          aria-label="Camera preview for employee face enrollment"
          style={{
            width: "100%",
            maxWidth: "480px",
            minHeight: "240px",
            background: "#0f172a",
            borderRadius: "12px",
            objectFit: "cover",
          }}
        />

        <p className="field-hint" style={{ textAlign: "center" }}>
          Ensure the employee is facing the camera, their face is well lit, and
          no other person is in the frame.
        </p>
      </div>

      <div className="employee-form-actions">
        {!cameraActive ? (
          <button
            className="primary-button"
            type="button"
            onClick={startCamera}
            disabled={faceLoading || Boolean(faceSuccess)}
          >
            Start Camera
          </button>
        ) : (
          <>
            <button
              className="secondary-button"
              type="button"
              onClick={stopCamera}
              disabled={faceLoading}
            >
              Stop Camera
            </button>

            <button
              className="primary-button"
              type="button"
              onClick={handleEnrollFace}
              disabled={faceLoading || Boolean(faceSuccess)}
            >
              {faceLoading ? "Enrolling Face..." : "Capture and Enroll Face"}
            </button>
          </>
        )}
      </div>

      {faceSuccess && (
        <div className="employee-form-actions">
          <button
            className="primary-button"
            type="button"
            onClick={continueToCreateLogin}
          >
            Continue to Create Login
          </button>
          <button
            className="secondary-button"
            type="button"
            onClick={() => {
              setFaceSuccess("");
              setFaceError("");
            }}
          >
            Enroll Again
          </button>
        </div>
      )}
    </section>
  );

  // Employee details
  const renderEmployeeDetails = (employee) => {
    const details = [
      ["Employee Code", employee.employee_code],
      ["First Name", employee.first_name],
      ["Last Name", employee.last_name],
      ["Email", employee.email],
      ["Phone", employee.phone],
      ["Department ID", employee.department_id],
      ["Designation ID", employee.designation_id],
      ["Manager ID", employee.manager_id],
      ["Joining Date", formatDate(employee.joining_date)],
      ["Employment Status", employee.employment_status],
      ["Account Status", employee.is_active ? "Active" : "Inactive"],
      [
        "Basic Salary",
        employee.basic_salary == null
          ? "—"
          : Number(employee.basic_salary).toLocaleString(),
      ],
      ["Created At", formatDate(employee.created_at)],
      ["Last Updated", formatDate(employee.updated_at)],
    ];

    return (
      <section className="employee-form-card">
        <div className="section-heading employee-form-heading">
          <div>
            <h2>Employee Details</h2>
            <p>
              {getEmployeeName(employee)} ({employee.employee_code || "—"})
            </p>
          </div>
          <button
            className="secondary-button"
            type="button"
            onClick={closeEmployeeDetails}
          >
            Back to Employees
          </button>
        </div>

        <div className="employee-form-grid">
          {details.map(([label, value]) => (
            <div className="form-field" key={label}>
              <span>{label}</span>
              <strong>{value ?? "—"}</strong>
            </div>
          ))}
        </div>

        {canManageEmployees && (
          <div className="employee-form-actions">
            <button
              className="primary-button"
              type="button"
              onClick={() => openEditEmployee(getEmployeeId(employee))}
              disabled={formLoading}
            >
              Edit Employee
            </button>
          </div>
        )}
      </section>
    );
  };

  // Employee login creation form
  const renderEmployeeAccountForm = () => (
    <section className="employee-form-card">
      <div className="section-heading employee-form-heading">
        <div>
          <h2>Create Employee Login</h2>
          <p>
            Create login credentials for{" "}
            <strong>{getEmployeeName(accountEmployee)}</strong>.
          </p>
        </div>
        <button
          className="secondary-button"
          type="button"
          onClick={closeAccountForm}
          disabled={accountLoading}
        >
          Back to Employees
        </button>
      </div>

      <div className="employee-form-grid">
        <div className="form-field">
          <span>Employee Code</span>
          <strong>{accountEmployee.employee_code || "—"}</strong>
        </div>
        <div className="form-field">
          <span>Login Email</span>
          <strong>{accountEmployee.email || "—"}</strong>
        </div>
        <div className="form-field">
          <span>Employment Status</span>
          <strong>{getEmployeeStatus(accountEmployee)}</strong>
        </div>
        <div className="form-field">
          <span>Face Enrollment</span>
          <strong>
            {faceEnrolledIds.has(String(getEmployeeId(accountEmployee)))
              ? "Enrolled"
              : "Not enrolled"}
          </strong>
        </div>
      </div>

      {accountError && (
        <div className="form-alert form-alert-error" role="alert">
          {accountError}
        </div>
      )}

      {accountSuccess && (
        <div className="form-alert form-alert-success" role="status">
          {accountSuccess}
        </div>
      )}

      {!accountSuccess && (
        <form onSubmit={handleCreateEmployeeAccount}>
          <div className="employee-form-grid">
            <label className="form-field">
              Initial Password *
              <input
                type="password"
                value={initialPassword}
                onChange={(event) => {
                  setInitialPassword(event.target.value);
                  setAccountError("");
                }}
                required
                minLength={8}
                maxLength={128}
                autoComplete="new-password"
                placeholder="Enter an initial password"
              />
              <small className="field-hint">
                Enter at least 8 characters. Any additional password rules
                enforced by the backend must also be satisfied.
              </small>
            </label>
          </div>

          <div className="employee-form-actions">
            <button
              className="secondary-button"
              type="button"
              onClick={closeAccountForm}
              disabled={accountLoading}
            >
              Cancel
            </button>
            <button
              className="primary-button"
              type="submit"
              disabled={
                accountLoading ||
                !faceEnrolledIds.has(String(getEmployeeId(accountEmployee)))
              }
              title={
                !faceEnrolledIds.has(String(getEmployeeId(accountEmployee)))
                  ? "Enroll the employee's face first."
                  : "Create login credentials."
              }
            >
              {accountLoading ? "Creating Account..." : "Create Login Account"}
            </button>
          </div>
        </form>
      )}

      {accountSuccess && (
        <div className="employee-form-actions">
          <button
            className="primary-button"
            type="button"
            onClick={closeAccountForm}
          >
            Back to Employees
          </button>
        </div>
      )}
    </section>
  );

  // Employees page
  const renderEmployees = () => (
    <section className="employees-page">
      {viewLoading ? (
        <div className="employee-form-card">
          <p>Loading employee details...</p>
        </div>
      ) : viewError && !viewingEmployee ? (
        <div className="employee-form-card">
          <div className="form-alert form-alert-error" role="alert">
            {viewError}
          </div>
          <button
            className="secondary-button"
            type="button"
            onClick={closeEmployeeDetails}
          >
            Back to Employees
          </button>
        </div>
      ) : viewingEmployee ? (
        renderEmployeeDetails(viewingEmployee)
      ) : faceEmployee ? (
        renderFaceEnrollment()
      ) : accountEmployee ? (
        renderEmployeeAccountForm()
      ) : !showEmployeeForm ? (
        <>
          <div className="section-heading">
            <div>
              <h2>Employees</h2>
              <p>View and manage employee records in your organization.</p>
            </div>
            {canManageEmployees && (
              <button
                className="primary-button"
                type="button"
                onClick={openEmployeeForm}
              >
                + Add Employee
              </button>
            )}
          </div>

          <div className="employee-list-meta">
            <span className="role-badge">{employeeTotal} Employees</span>
            <button
              className="secondary-button"
              type="button"
              onClick={() => fetchEmployees(employeePage)}
              disabled={employeesLoading}
            >
              Refresh list
            </button>
          </div>

          {employeesLoading && <p>Loading employees...</p>}
          {employeesError && <p className="error-message">{employeesError}</p>}

          {!employeesLoading && !employeesError && (
            <>
              <div className="employee-table-wrapper">
                <table className="employee-table">
                  <thead>
                    <tr>
                      <th>Employee Code</th>
                      <th>Employee</th>
                      <th>Email</th>
                      <th>Department ID</th>
                      <th>Designation ID</th>
                      <th>Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {employees.length === 0 ? (
                      <tr>
                        <td colSpan={7}>No employee records found.</td>
                      </tr>
                    ) : (
                      employees.map((employee, index) => {
                        const employeeId = getEmployeeId(employee);
                        const faceIsEnrolled = faceEnrolledIds.has(
                          String(employeeId)
                        );

                        return (
                          <tr key={employeeId || index}>
                            <td>{employee.employee_code || "—"}</td>
                            <td>{getEmployeeName(employee)}</td>
                            <td>{employee.email || "—"}</td>
                            <td>{employee.department_id || "—"}</td>
                            <td>{employee.designation_id || "—"}</td>
                            <td>
                              <span className="employee-status">
                                {getEmployeeStatus(employee)}
                              </span>
                            </td>
                            <td>
                              <div className="department-actions">
                                <button
                                  className="secondary-button"
                                  type="button"
                                  onClick={() => openViewEmployee(employeeId)}
                                  disabled={viewLoading}
                                >
                                  View
                                </button>

                                {canManageEmployees && (
                                  <>
                                    <button
                                      className="secondary-button"
                                      type="button"
                                      onClick={() => openEditEmployee(employeeId)}
                                      disabled={formLoading}
                                    >
                                      Edit
                                    </button>

                                    <button
                                      className="secondary-button"
                                      type="button"
                                      onClick={() => openFaceEnrollment(employee)}
                                      disabled={
                                        faceLoading ||
                                        getEmployeeStatus(employee) !== "Active"
                                      }
                                      title="Capture or update this employee's face."
                                    >
                                      {faceIsEnrolled
                                        ? "Re-enroll Face"
                                        : "Enroll Face"}
                                    </button>

                                    <button
                                      className="primary-button"
                                      type="button"
                                      onClick={() => {
                                        if (!faceIsEnrolled) {
                                          setEmployeesError(
                                            "Enroll this employee's face before creating a login."
                                          );
                                          return;
                                        }

                                        setEmployeesError("");
                                        openAccountForm(employee);
                                      }}
                                      disabled={
                                        accountLoading ||
                                        getEmployeeStatus(employee) !== "Active" ||
                                        !employee.email ||
                                        !faceIsEnrolled
                                      }
                                      title={
                                        !faceIsEnrolled
                                          ? "Enroll the employee's face first."
                                          : getEmployeeStatus(employee) !== "Active"
                                            ? "Only active employees can receive login accounts."
                                            : !employee.email
                                              ? "An email address is required."
                                              : "Create login credentials for this employee."
                                      }
                                    >
                                      Create Login
                                    </button>
                                  </>
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>

              <div className="pagination-controls">
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() =>
                    setEmployeePage((page) => Math.max(1, page - 1))
                  }
                  disabled={employeePage <= 1 || employeesLoading}
                >
                  Previous
                </button>
                <span>Page {employeePage}</span>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => setEmployeePage((page) => page + 1)}
                  disabled={
                    employeesLoading || employeePage * 20 >= employeeTotal
                  }
                >
                  Next
                </button>
              </div>
            </>
          )}
        </>
      ) : (
        renderEmployeeForm()
      )}
    </section>
  );

  // Department management page
  const renderDepartments = () => (
    <section className="employees-page">
      {!showDepartmentForm ? (
        <>
          <div className="section-heading">
            <div>
              <h2>Departments</h2>
              <p>Organize and manage your company's departments.</p>
            </div>
            {canManageOrganization && (
              <button
                className="primary-button"
                type="button"
                onClick={() => openDepartmentForm()}
              >
                + Add Department
              </button>
            )}
          </div>

          {departmentsError && (
            <div className="form-alert form-alert-error" role="alert">
              {departmentsError}
            </div>
          )}
          {departmentSuccess && (
            <div className="form-alert form-alert-success" role="status">
              {departmentSuccess}
            </div>
          )}

          <div className="department-toolbar">
            <label className="department-toggle">
              <input
                type="checkbox"
                checked={showInactiveDepartments}
                onChange={(event) =>
                  setShowInactiveDepartments(event.target.checked)
                }
              />
              Show inactive departments
            </label>
            <button
              className="secondary-button"
              type="button"
              onClick={fetchDepartmentList}
              disabled={departmentsLoading}
            >
              {departmentsLoading ? "Loading..." : "Refresh Departments"}
            </button>
          </div>

          {departmentsLoading ? (
            <p>Loading departments...</p>
          ) : (
            <div className="employee-table-wrapper">
              <table className="employee-table">
                <thead>
                  <tr>
                    <th>Code</th>
                    <th>Department</th>
                    <th>Description</th>
                    <th>Status</th>
                    {canManageOrganization && <th>Actions</th>}
                  </tr>
                </thead>
                <tbody>
                  {departmentsList.length === 0 ? (
                    <tr>
                      <td colSpan={canManageOrganization ? 5 : 4}>
                        No departments found.
                      </td>
                    </tr>
                  ) : (
                    departmentsList.map((department) => (
                      <tr key={department.id}>
                        <td>{department.code}</td>
                        <td>{department.name}</td>
                        <td>{department.description || "—"}</td>
                        <td>
                          <span
                            className="employee-status"
                            style={
                              department.is_active
                                ? {}
                                : { background: "#f1f5f9", color: "#64748b" }
                            }
                          >
                            {department.is_active ? "Active" : "Inactive"}
                          </span>
                        </td>
                        {canManageOrganization && (
                          <td>
                            <div className="department-actions">
                              <button
                                className="secondary-button"
                                type="button"
                                onClick={() => openDepartmentForm(department)}
                              >
                                Edit
                              </button>
                              <button
                                className="secondary-button"
                                type="button"
                                onClick={() => handleDepartmentStatus(department)}
                              >
                                {department.is_active ? "Deactivate" : "Activate"}
                              </button>
                            </div>
                          </td>
                        )}
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </>
      ) : (
        <section className="employee-form-card">
          <div className="section-heading employee-form-heading">
            <div>
              <h2>{editingDepartmentId ? "Edit Department" : "Add Department"}</h2>
              <p>Enter the department details below.</p>
            </div>
            <button
              className="secondary-button"
              type="button"
              onClick={closeDepartmentForm}
              disabled={departmentSaving}
            >
              Cancel
            </button>
          </div>

          {departmentsError && (
            <div className="form-alert form-alert-error" role="alert">
              {departmentsError}
            </div>
          )}

          <form onSubmit={handleSaveDepartment}>
            <div className="employee-form-grid">
              <label className="form-field">
                Department Name *
                <input
                  name="name"
                  value={departmentForm.name}
                  onChange={handleDepartmentFieldChange}
                  required
                  maxLength={120}
                  placeholder="e.g. Human Resources"
                />
              </label>
              <label className="form-field">
                Department Code *
                <input
                  name="code"
                  value={departmentForm.code}
                  onChange={handleDepartmentFieldChange}
                  required
                  maxLength={120}
                  placeholder="e.g. HR"
                />
              </label>
              <label className="form-field department-description-field">
                Description
                <textarea
                  name="description"
                  value={departmentForm.description}
                  onChange={handleDepartmentFieldChange}
                  maxLength={1000}
                  rows={4}
                  placeholder="Optional department description"
                />
              </label>
            </div>

            <div className="employee-form-actions">
              <button
                className="secondary-button"
                type="button"
                onClick={closeDepartmentForm}
                disabled={departmentSaving}
              >
                Cancel
              </button>
              <button
                className="primary-button"
                type="submit"
                disabled={departmentSaving || !canManageOrganization}
              >
                {departmentSaving
                  ? "Saving..."
                  : editingDepartmentId
                    ? "Save Changes"
                    : "Create Department"}
              </button>
            </div>
          </form>
        </section>
      )}
    </section>
  );

  // Designation management page
  const renderDesignations = () => (
    <section className="employees-page">
      {!showDesignationForm ? (
        <>
          <div className="section-heading">
            <div>
              <h2>Designations</h2>
              <p>Manage job titles and associate them with departments.</p>
            </div>
            {canManageOrganization && (
              <button
                className="primary-button"
                type="button"
                onClick={() => openDesignationForm()}
              >
                + Add Designation
              </button>
            )}
          </div>

          {designationError && (
            <div className="form-alert form-alert-error" role="alert">
              {designationError}
            </div>
          )}
          {designationSuccess && (
            <div className="form-alert form-alert-success" role="status">
              {designationSuccess}
            </div>
          )}

          <div className="designation-toolbar">
            <label className="form-field designation-filter">
              Filter by Department
              <select
                value={designationDepartmentFilter}
                onChange={(event) =>
                  setDesignationDepartmentFilter(event.target.value)
                }
              >
                <option value="">All departments</option>
                {designationDepartments.map((department) => (
                  <option key={department.id} value={department.id}>
                    {department.name} ({department.code})
                  </option>
                ))}
              </select>
            </label>

            <label className="department-toggle">
              <input
                type="checkbox"
                checked={showInactiveDesignations}
                onChange={(event) =>
                  setShowInactiveDesignations(event.target.checked)
                }
              />
              Show inactive designations
            </label>

            <button
              className="secondary-button"
              type="button"
              onClick={refreshDesignations}
              disabled={designationLoading}
            >
              {designationLoading ? "Loading..." : "Refresh"}
            </button>
          </div>

          {designationLoading ? (
            <p>Loading designations...</p>
          ) : (
            <div className="employee-table-wrapper">
              <table className="employee-table">
                <thead>
                  <tr>
                    <th>Code</th>
                    <th>Designation</th>
                    <th>Department</th>
                    <th>Description</th>
                    <th>Status</th>
                    {canManageOrganization && <th>Actions</th>}
                  </tr>
                </thead>
                <tbody>
                  {designationList.length === 0 ? (
                    <tr>
                      <td colSpan={canManageOrganization ? 6 : 5}>
                        No designations found.
                      </td>
                    </tr>
                  ) : (
                    designationList.map((designation) => (
                      <tr key={designation.id}>
                        <td>{designation.code}</td>
                        <td>{designation.name}</td>
                        <td>
                          {getDepartmentName(
                            designation.department_id,
                            designationDepartments
                          )}
                        </td>
                        <td>{designation.description || "—"}</td>
                        <td>
                          <span
                            className="employee-status"
                            style={
                              designation.is_active
                                ? {}
                                : { background: "#f1f5f9", color: "#64748b" }
                            }
                          >
                            {designation.is_active ? "Active" : "Inactive"}
                          </span>
                        </td>
                        {canManageOrganization && (
                          <td>
                            <div className="department-actions">
                              <button
                                className="secondary-button"
                                type="button"
                                onClick={() => openDesignationForm(designation)}
                              >
                                Edit
                              </button>
                              <button
                                className="secondary-button"
                                type="button"
                                onClick={() => handleDesignationStatus(designation)}
                              >
                                {designation.is_active ? "Deactivate" : "Activate"}
                              </button>
                            </div>
                          </td>
                        )}
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </>
      ) : (
        <section className="employee-form-card">
          <div className="section-heading employee-form-heading">
            <div>
              <h2>{editingDesignationId ? "Edit Designation" : "Add Designation"}</h2>
              <p>
                {editingDesignationId
                  ? "Update the designation details below."
                  : "Create a designation under an active department."}
              </p>
            </div>
            <button
              className="secondary-button"
              type="button"
              onClick={closeDesignationForm}
              disabled={designationSaving}
            >
              Cancel
            </button>
          </div>

          {designationError && (
            <div className="form-alert form-alert-error" role="alert">
              {designationError}
            </div>
          )}

          <form onSubmit={handleSaveDesignation}>
            <div className="employee-form-grid">
              <label className="form-field">
                Designation Name *
                <input
                  name="name"
                  value={designationForm.name}
                  onChange={handleDesignationFieldChange}
                  required
                  maxLength={120}
                  placeholder="e.g. Software Engineer"
                />
              </label>
              <label className="form-field">
                Designation Code *
                <input
                  name="code"
                  value={designationForm.code}
                  onChange={handleDesignationFieldChange}
                  required
                  maxLength={120}
                  placeholder="e.g. SE"
                />
              </label>
              <label className="form-field">
                Department *
                <select
                  name="department_id"
                  value={designationForm.department_id}
                  onChange={handleDesignationFieldChange}
                  required
                  disabled={Boolean(editingDesignationId)}
                >
                  <option value="">Select department</option>
                  {designationDepartments
                    .filter(
                      (item) =>
                        item.is_active ||
                        item.id === designationForm.department_id
                    )
                    .map((department) => (
                      <option key={department.id} value={department.id}>
                        {department.name} ({department.code})
                        {department.is_active ? "" : " — Inactive"}
                      </option>
                    ))}
                </select>
                {editingDesignationId && (
                  <small className="field-hint">
                    The department cannot be changed when editing a designation.
                  </small>
                )}
              </label>
              <label className="form-field department-description-field">
                Description
                <textarea
                  name="description"
                  value={designationForm.description}
                  onChange={handleDesignationFieldChange}
                  maxLength={1000}
                  rows={4}
                  placeholder="Optional designation description"
                />
              </label>
            </div>

            <div className="employee-form-actions">
              <button
                className="secondary-button"
                type="button"
                onClick={closeDesignationForm}
                disabled={designationSaving}
              >
                Cancel
              </button>
              <button
                className="primary-button"
                type="submit"
                disabled={designationSaving || !canManageOrganization}
              >
                {designationSaving
                  ? "Saving..."
                  : editingDesignationId
                    ? "Save Changes"
                    : "Create Designation"}
              </button>
            </div>
          </form>
        </section>
      )}
    </section>
  );

  const renderHRAccountForm = () => (
  <section className="employee-form-card">
    <div className="section-heading employee-form-heading">
      <div>
        <h2>Create HR Account</h2>
        <p>
          Create login credentials for a new Human Resources user.
        </p>
      </div>

      <button
        className="secondary-button"
        type="button"
        onClick={closeHRAccountForm}
        disabled={hrAccountLoading}
      >
        Back
      </button>
    </div>

    {hrAccountError && (
      <div className="form-alert form-alert-error" role="alert">
        {hrAccountError}
      </div>
    )}

    {hrAccountSuccess && (
      <div className="form-alert form-alert-success" role="status">
        {hrAccountSuccess}
      </div>
    )}

    <form onSubmit={handleCreateHRAccount}>
      <div className="employee-form-grid">
        <label className="form-field">
          HR Email Address *
          <input
            type="email"
            value={hrEmail}
            onChange={(event) => {
              setHrEmail(event.target.value);
              setHrAccountError("");
              setHrAccountSuccess("");
            }}
            required
            maxLength={254}
            autoComplete="email"
            placeholder="hr@company.com"
            disabled={hrAccountLoading}
          />
        </label>

        <label className="form-field">
          Initial Password *
          <input
            type="password"
            value={hrInitialPassword}
            onChange={(event) => {
              setHrInitialPassword(event.target.value);
              setHrAccountError("");
              setHrAccountSuccess("");
            }}
            required
            minLength={8}
            maxLength={72}
            autoComplete="new-password"
            placeholder="Enter an initial password"
            disabled={hrAccountLoading}
          />

          <small className="field-hint">
            Use at least 8 characters. The backend also limits passwords
            to 72 UTF-8 bytes.
          </small>
        </label>
      </div>

      <div className="employee-form-actions">
        <button
          className="secondary-button"
          type="button"
          onClick={closeHRAccountForm}
          disabled={hrAccountLoading}
        >
          Cancel
        </button>

        <button
          className="primary-button"
          type="submit"
          disabled={hrAccountLoading}
        >
          {hrAccountLoading ? "Creating HR Account..." : "Create HR Account"}
        </button>
      </div>
    </form>
  </section>
  );
  
    // Leave Management page
  const renderLeaveManagement = () => {
    const isEmployee = role === "Employee";
    const isMyLeave = activePage === "My Leave";

    const visibleRequests =
      isEmployee || leaveTypeFilter === "All"
        ? leaveRequests
        : leaveRequests.filter(
            (request) => request.leave_type === leaveTypeFilter
          );

    const today = new Date();
    const todayString = [
      today.getFullYear(),
      String(today.getMonth() + 1).padStart(2, "0"),
      String(today.getDate()).padStart(2, "0"),
    ].join("-");

    const statusClass = (value) =>
      `employee-status leave-status-${String(value || "")
        .toLowerCase()
        .replace(/\s+/g, "-")}`;

    return (
      <section className="employees-page">
        <div className="section-heading">
          <div>
            <h2>{isEmployee ? "My Leave" : "Leave Management"}</h2>
            <p>
              {isEmployee
                ? "Submit leave applications and track their status."
                : "Review employee leave applications and manage decisions."}
            </p>
          </div>

          <button
            className="secondary-button"
            type="button"
            onClick={fetchLeaveRequests}
            disabled={leaveLoading}
          >
            {leaveLoading ? "Loading..." : "Refresh"}
          </button>
        </div>

        {leaveError && (
          <div className="form-alert form-alert-error" role="alert">
            {leaveError}
          </div>
        )}

        {leaveSuccess && (
          <div className="form-alert form-alert-success" role="status">
            {leaveSuccess}
          </div>
        )}

        {isEmployee && (
          <section className="employee-form-card">
            <div className="section-heading">
              <div>
                <h2>Apply for Leave</h2>
                <p>
                  Select your dates and provide a reason. Working days are
                  calculated by the server.
                </p>
              </div>
            </div>

            <form onSubmit={handleApplyForLeave}>
              <div className="employee-form-grid">
                <label className="form-field">
                  Leave Type *
                  <select
                    value={leaveForm.leave_type}
                    onChange={(event) =>
                      setLeaveForm((previous) => ({
                        ...previous,
                        leave_type: event.target.value,
                      }))
                    }
                    required
                  >
                    <option value="Annual">Annual</option>
                    <option value="Sick">Sick</option>
                    <option value="Casual">Casual</option>
                    <option value="Unpaid">Unpaid</option>
                  </select>
                </label>

                <label className="form-field">
                  Start Date *
                  <input
                    type="date"
                    value={leaveForm.start_date}
                    min={todayString}
                    onChange={(event) =>
                      setLeaveForm((previous) => ({
                        ...previous,
                        start_date: event.target.value,
                        end_date:
                          previous.end_date &&
                          previous.end_date < event.target.value
                            ? event.target.value
                            : previous.end_date,
                      }))
                    }
                    required
                  />
                </label>

                <label className="form-field">
                  End Date *
                  <input
                    type="date"
                    value={leaveForm.end_date}
                    min={leaveForm.start_date || todayString}
                    onChange={(event) =>
                      setLeaveForm((previous) => ({
                        ...previous,
                        end_date: event.target.value,
                      }))
                    }
                    required
                  />
                </label>

                <label className="form-field department-description-field">
                  Reason for Leave *
                  <textarea
                    value={leaveForm.reason}
                    onChange={(event) =>
                      setLeaveForm((previous) => ({
                        ...previous,
                        reason: event.target.value,
                      }))
                    }
                    required
                    minLength={3}
                    maxLength={1000}
                    rows={4}
                    placeholder="Explain why you need leave..."
                  />
                </label>
              </div>

              <div className="employee-form-actions">
                <button
                  className="primary-button"
                  type="submit"
                  disabled={leaveSubmitting}
                >
                  {leaveSubmitting ? "Submitting..." : "Submit Leave Request"}
                </button>
              </div>
            </form>
          </section>
        )}

        <div className="section-heading" style={{ marginTop: "28px" }}>
          <div>
            <h2>{isEmployee ? "My Applications" : "Leave Requests"}</h2>
            <p>{leaveTotal} request(s) found.</p>
          </div>
        </div>

        {!isEmployee && (
          <div className="designation-toolbar">
            <label className="form-field designation-filter">
              Filter by Status
              <select
                value={leaveStatusFilter}
                onChange={(event) => {
                  setLeaveStatusFilter(event.target.value);
                  setLeavePage(1);
                }}
              >
                <option value="All">All statuses</option>
                <option value="Pending">Pending</option>
                <option value="Approved">Approved</option>
                <option value="Rejected">Rejected</option>
                <option value="Cancelled">Cancelled</option>
              </select>
            </label>

            <label className="form-field designation-filter">
              Filter by Leave Type
              <select
                value={leaveTypeFilter}
                onChange={(event) => setLeaveTypeFilter(event.target.value)}
              >
                <option value="All">All leave types</option>
                <option value="Annual">Annual</option>
                <option value="Sick">Sick</option>
                <option value="Casual">Casual</option>
                <option value="Unpaid">Unpaid</option>
              </select>
            </label>
          </div>
        )}

        {leaveLoading ? (
          <p>Loading leave requests...</p>
        ) : (
          <div className="employee-table-wrapper">
            <table className="employee-table">
              <thead>
                <tr>
                  {!isEmployee && <th>Employee ID</th>}
                  <th>Leave Type</th>
                  <th>Start Date</th>
                  <th>End Date</th>
                  <th>Working Days</th>
                  <th>Reason</th>
                  <th>Status</th>
                  <th>Review Note</th>
                  {isEmployee ? <th>Action</th> : <th>Review</th>}
                </tr>
              </thead>

              <tbody>
                {visibleRequests.length === 0 ? (
                  <tr>
                    <td colSpan={isEmployee ? 8 : 9}>
                      No leave requests found.
                    </td>
                  </tr>
                ) : (
                  visibleRequests.map((request) => (
                    <tr key={request.id}>
                      {!isEmployee && (
                        <td>{request.employee_id || "—"}</td>
                      )}
                      <td>{request.leave_type}</td>
                      <td>{formatDate(request.start_date)}</td>
                      <td>{formatDate(request.end_date)}</td>
                      <td>{request.total_days ?? "—"}</td>
                      <td style={{ minWidth: "180px", whiteSpace: "normal" }}>
                        {request.reason}
                      </td>
                      <td>
                        <span className={statusClass(request.status)}>
                          {request.status}
                        </span>
                      </td>
                      <td style={{ minWidth: "150px", whiteSpace: "normal" }}>
                        {request.review_note || "—"}
                      </td>
                      <td>
                        {isEmployee ? (
                          request.status === "Pending" ? (
                            <button
                              className="secondary-button"
                              type="button"
                              onClick={() => handleCancelLeave(request.id)}
                            >
                              Cancel
                            </button>
                          ) : (
                            "—"
                          )
                        ) : request.status === "Pending" ? (
                          <div
                            style={{
                              display: "flex",
                              flexDirection: "column",
                              gap: "8px",
                              minWidth: "160px",
                            }}
                          >
                            <textarea
                              value={
                                reviewingLeaveId === request.id
                                  ? reviewNote
                                  : undefined
                              }
                              placeholder="Optional review note"
                              rows={2}
                              maxLength={1000}
                              onFocus={() => {
                                setReviewingLeaveId(request.id);
                                setReviewNote("");
                              }}
                              onChange={(event) => {
                                setReviewingLeaveId(request.id);
                                setReviewNote(event.target.value);
                              }}
                              disabled={
                                reviewingLeaveId !== null &&
                                reviewingLeaveId !== request.id
                              }
                            />
                            <button
                              className="primary-button"
                              type="button"
                              disabled={reviewingLeaveId !== null}
                              onClick={() =>
                                handleReviewLeave(request.id, "Approved")
                              }
                            >
                              Approve
                            </button>
                            <button
                              className="secondary-button"
                              type="button"
                              disabled={reviewingLeaveId !== null}
                              onClick={() =>
                                handleReviewLeave(request.id, "Rejected")
                              }
                            >
                              Reject
                            </button>
                          </div>
                        ) : (
                          "—"
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        <div className="pagination-controls">
          <button
            className="secondary-button"
            type="button"
            onClick={() => setLeavePage((page) => Math.max(1, page - 1))}
            disabled={leavePage <= 1 || leaveLoading}
          >
            Previous
          </button>

          <span>
            Page {leavePage} of {Math.max(1, Math.ceil(leaveTotal / 20))}
          </span>

          <button
            className="secondary-button"
            type="button"
            onClick={() => setLeavePage((page) => page + 1)}
            disabled={leaveLoading || leavePage * 20 >= leaveTotal}
          >
            Next
          </button>
        </div>
      </section>
    );
  };

  
  const renderPayroll = () => {
    const isEmployee = role === "Employee";

    const formatMoney = (value) =>
      new Intl.NumberFormat("en-PK", {
        style: "currency",
        currency: "PKR",
        maximumFractionDigits: 2,
      }).format(Number(value ?? 0));

    const formatDays = (value) =>
      Number(value ?? 0).toLocaleString("en-PK", {
        maximumFractionDigits: 2,
      });

    return (
      <section className="employees-page">
        <div className="section-heading">
          <div>
            <h2>{isEmployee ? "My Payroll" : "Payroll Management"}</h2>
            <p>
              {isEmployee
                ? "Review your salary, attendance deductions, and payslip status."
                : "View monthly payroll records and manage payroll finalization."}
            </p>
          </div>

          <button
            className="secondary-button"
            type="button"
            onClick={() => fetchPayrollRecords(payrollPage)}
            disabled={payrollLoading}
          >
            {payrollLoading ? "Loading..." : "Refresh"}
          </button>
        </div>

        {payrollError && (
          <div className="form-alert form-alert-error" role="alert">
            {payrollError}
          </div>
        )}

        {payrollSuccess && (
          <div className="form-alert form-alert-success" role="status">
            {payrollSuccess}
          </div>
        )}

        {role === "Admin" && (
          <section className="employee-form-card">
            <h3>Generate Monthly Payroll</h3>
            <p>
              Generate draft payroll for active employees for the selected
              month.
            </p>

            <form onSubmit={handleGeneratePayroll}>
              <div className="employee-form-grid">
                <label className="form-field">
                  Payroll Month *
                  <input
                    type="month"
                    value={payrollMonth}
                    onChange={(event) =>
                      setPayrollMonth(event.target.value)
                    }
                    required
                    disabled={payrollGenerating}
                  />
                </label>
              </div>

              <div className="employee-form-actions">
                <button
                  className="primary-button"
                  type="submit"
                  disabled={payrollGenerating}
                >
                  {payrollGenerating
                    ? "Generating..."
                    : "Generate Payroll"}
                </button>
              </div>
            </form>
          </section>
        )}

        {!isEmployee && (
          <div className="designation-toolbar">
            <label className="form-field designation-filter">
              Filter by Payroll Month
              <input
                type="month"
                value={payrollFilterMonth}
                onChange={(event) => {
                  setPayrollFilterMonth(event.target.value);
                  setPayrollPage(1);
                }}
              />
            </label>

            <button
              className="secondary-button"
              type="button"
              onClick={() => fetchPayrollRecords(1)}
              disabled={payrollLoading}
            >
              Apply Filter
            </button>
          </div>
        )}

        <div className="section-heading" style={{ marginTop: "24px" }}>
          <div>
            <h2>Payroll Records</h2>
            <p>{payrollTotal} record(s) found.</p>
          </div>
        </div>

        {payrollLoading ? (
          <p>Loading payroll records...</p>
        ) : (
          <div className="employee-table-wrapper">
            <table className="employee-table">
              <thead>
                <tr>
                  <th>Month</th>
                  {!isEmployee && <th>Employee ID</th>}
                  <th>Basic Salary</th>
                  <th>HRA</th>
                  <th>Medical</th>
                  <th>Gross Salary</th>
                  <th>Present Days</th>
                  <th>Absent Days</th>
                  <th>Total Deductions</th>
                  <th>Net Salary</th>
                  <th>Status</th>
                  {role === "Admin" && <th>Actions</th>}
                </tr>
              </thead>

              <tbody>
                {payrollRecords.length === 0 ? (
                  <tr>
                    <td colSpan={role === "Admin" ? 12 : isEmployee ? 10 : 11}>
                      No payroll records found.
                    </td>
                  </tr>
                ) : (
                  payrollRecords.map((record) => (
                    <tr key={record.id}>
                      <td>{record.payroll_month}</td>
                      {!isEmployee && (
                        <td>{record.employee_id || "—"}</td>
                      )}
                      <td>{formatMoney(record.basic_salary)}</td>
                      <td>{formatMoney(record.hra)}</td>
                      <td>{formatMoney(record.medical_allowance)}</td>
                      <td>{formatMoney(record.gross_salary)}</td>
                      <td>{formatDays(record.present_days)}</td>
                      <td>{formatDays(record.absent_days)}</td>
                      <td>{formatMoney(record.total_deductions)}</td>
                      <td>
                        <strong>{formatMoney(record.net_salary)}</strong>
                      </td>
                      <td>
                        <span
                          className="employee-status"
                          style={
                            record.status === "Finalized"
                              ? {
                                  background: "#dcfce7",
                                  color: "#166534",
                                }
                              : {
                                  background: "#fef3c7",
                                  color: "#92400e",
                                }
                          }
                        >
                          {record.status}
                        </span>
                      </td>

                      {role === "Admin" && (
                        <td>
                          {record.status === "Draft" ? (
                            <button
                              className="primary-button"
                              type="button"
                              onClick={() =>
                                handleFinalizePayroll(record.id)
                              }
                              disabled={
                                finalizingPayrollId !== null ||
                                payrollGenerating
                              }
                            >
                              {finalizingPayrollId === record.id
                                ? "Finalizing..."
                                : "Finalize"}
                            </button>
                          ) : (
                            "—"
                          )}
                        </td>
                      )}
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        <div className="pagination-controls">
          <button
            className="secondary-button"
            type="button"
            onClick={() => {
              const nextPage = Math.max(1, payrollPage - 1);
              setPayrollPage(nextPage);
              fetchPayrollRecords(nextPage);
            }}
            disabled={payrollPage <= 1 || payrollLoading}
          >
            Previous
          </button>

          <span>
            Page {payrollPage} of{" "}
            {Math.max(1, Math.ceil(payrollTotal / 20))}
          </span>

          <button
            className="secondary-button"
            type="button"
            onClick={() => {
              const nextPage = payrollPage + 1;
              setPayrollPage(nextPage);
              fetchPayrollRecords(nextPage);
            }}
            disabled={payrollLoading || payrollPage * 20 >= payrollTotal}
          >
            Next
          </button>
        </div>
      </section>
    );
  };

  // Audit Logs page
const renderAuditLogs = () => {
  const formatAuditDate = (value) => {
    if (!value) return "—";

    const date = new Date(value);

    return Number.isNaN(date.getTime())
      ? String(value)
      : date.toLocaleString();
  };

  return (
    <section className="employees-page">
      <div className="section-heading">
        <div>
          <h2>Audit Logs</h2>
          <p>
            Review recorded actions performed within your organization.
          </p>
        </div>

        <button
          className="secondary-button"
          type="button"
          onClick={() => fetchAuditLogs(auditPage)}
          disabled={auditLoading}
        >
          {auditLoading ? "Loading..." : "Refresh"}
        </button>
      </div>

      {auditError && (
        <div className="form-alert form-alert-error" role="alert">
          {auditError}
        </div>
      )}

      <div className="section-heading" style={{ marginTop: "24px" }}>
        <div>
          <h2>Activity History</h2>
          <p>{auditTotal} record(s) found.</p>
        </div>
      </div>

      {auditLoading ? (
        <p>Loading audit logs...</p>
      ) : (
        <div className="employee-table-wrapper">
          <table className="employee-table">
            <thead>
              <tr>
                <th>Date &amp; Time</th>
                <th>Actor Email</th>
                <th>Role</th>
                <th>Action</th>
                <th>Target Type</th>
                <th>Target ID</th>
                <th>Details</th>
              </tr>
            </thead>

            <tbody>
              {auditLogs.length === 0 ? (
                <tr>
                  <td colSpan={7}>No audit logs found.</td>
                </tr>
              ) : (
                auditLogs.map((log, index) => (
                  <tr key={log.id || log._id || index}>
                    <td>{formatAuditDate(log.created_at)}</td>
                    <td>{log.actor_email || "—"}</td>
                    <td>{log.actor_role || "—"}</td>
                    <td>{log.action || "—"}</td>
                    <td>{log.target_type || "—"}</td>
                    <td>{log.target_id || "—"}</td>
                    <td
                      style={{
                        minWidth: "200px",
                        whiteSpace: "normal",
                      }}
                    >
                      {log.details &&
                      typeof log.details === "object"
                        ? JSON.stringify(log.details)
                        : log.details || "—"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      <div className="pagination-controls">
        <button
          className="secondary-button"
          type="button"
          onClick={() =>
            setAuditPage((page) => Math.max(1, page - 1))
          }
          disabled={auditPage <= 1 || auditLoading}
        >
          Previous
        </button>

        <span>
          Page {auditPage} of{" "}
          {Math.max(1, Math.ceil(auditTotal / 20))}
        </span>

        <button
          className="secondary-button"
          type="button"
          onClick={() => setAuditPage((page) => page + 1)}
          disabled={auditLoading || auditPage * 20 >= auditTotal}
        >
          Next
        </button>
      </div>
    </section>
  );
};


  const renderPlaceholder = () => (
    <section className="employees-page">
      <div className="section-heading">
        <div>
          <h2>{activePage}</h2>
          <p>This section will be implemented next.</p>
        </div>
        <span className="role-badge">{role}</span>
      </div>
    </section>
  );

  return (
    <div className="dashboard-layout">
      <aside className="dashboard-sidebar">
        <div className="sidebar-brand">
          <span className="sidebar-logo">H</span>
          <div>
            <strong>HCM Lite</strong>
            <small>HR Management</small>
          </div>
        </div>

        <p className="sidebar-label">WORKSPACE</p>

        <nav className="sidebar-nav">
          {navigation.map((item) => (
            <button
              key={item}
              className={`nav-item ${activePage === item ? "active" : ""}`}
              type="button"
              onClick={() => {
                stopCamera();
                setActivePage(item);

                setShowEmployeeForm(false);
                setEditingEmployeeId(null);
                setEmployeeForm(initialEmployeeForm);
                setViewingEmployee(null);
                setViewError("");
                setFormError("");
                setFormSuccess("");

                // Close face enrollment when changing pages.
                setFaceEmployee(null);
                setFaceError("");
                setFaceSuccess("");

                // Close the login-account form when changing pages.
                setAccountEmployee(null);
                setInitialPassword("");
                setAccountError("");
                setAccountSuccess("");

                setShowDepartmentForm(false);
                setEditingDepartmentId(null);
                setDepartmentForm(initialDepartmentForm);

                setShowDesignationForm(false);
                setEditingDesignationId(null);
                setDesignationForm(initialDesignationForm);
                setDesignationError("");
                setDesignationSuccess("");
                setShowHRAccountForm(false);
              }}
            >
              <span className="nav-dot" />
              {item}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="sidebar-user">
            <span className="user-avatar">
              {user?.email?.charAt(0).toUpperCase() || "U"}
            </span>
            <div className="sidebar-user-info">
              <strong>{user?.email}</strong>
              <small>{role}</small>
            </div>
          </div>

          <button
            className="logout-button"
            type="button"
            onClick={() => {
              stopCamera();
              onLogout();
            }}
          >
            Sign out
          </button>
        </div>
      </aside>

      <main className="dashboard-main">
        <header className="dashboard-header">
          <div>
            <span className="header-eyebrow">YOUR WORKSPACE</span>
            <h1>{activePage}</h1>
          </div>
          <div className="header-account">
            <span className="status-indicator" />
            <span>{role}</span>
          </div>
        </header>

        <section className="dashboard-content">
          {activePage === "Dashboard" ? (
            renderDashboard()
          ) : activePage === "Employees" ? (
            renderEmployees()
          ) : activePage === "Create HR Account" && role === "Admin" ? (
  renderHRAccountForm()
          ) : activePage === "Departments" ? (
            renderDepartments()
          ) : activePage === "Designations" ? (
          renderDesignations()
          ) : activePage === "Attendance" ||
              activePage === "My Attendance" ? (
              <Attendance role={role} />
          
          ) : activePage === "Leave Management" ||
              activePage === "My Leave" ? (
            renderLeaveManagement()
          ) : activePage === "Payroll" ||
          activePage === "My Payroll" ? (
          renderPayroll()
          ) : activePage === "Audit Logs" && role === "Admin" ? (
  renderAuditLogs()
          ) : activePage === "AI Assistant" ? (
          <AIAssistant />
          ) : (
          renderPlaceholder()
          )}


          <footer className="dashboard-footer">
            HCM Lite · Human Capital Management
          </footer>
        </section>
      </main>
    </div>
  );
}

export default Dashboard;