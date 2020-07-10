/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or
 *     any later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package project;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.FileReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.ObjectInputStream;
import java.io.ObjectOutputStream;
import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.LinkedHashMap;

import javafx.scene.control.Alert;
import javafx.scene.control.Alert.AlertType;
import agent.InputAgent;
import agent.InputAgentBands;
import agent.InputAgentDos;
import agent.InputAgentGeo;
import agent.InputAgentMd;
import agent.InputAgentNscf;
import agent.InputAgentOpt;
import agent.InputAgentScf;
import agent.InputAgentTddft;
import app.input.CellParameter;
import app.input.geo.Atom;

import com.consts.Constants.EnumCalc;
import com.consts.Constants.EnumStep;
import com.error.ErrorMsg;
import com.error.ShowAlert;
import com.programconst.DefaultFileNames;
import com.pseudopot.PseudoPotential;

import input.ContainerInputString;
import input.QeInput;

public class ProjectManager{
	public String workSpacePath;
	private String pseudoLibPath;
	public String qePath;
	private LinkedHashMap<String, Project> projectDict;
	private String activeProjKey;
	
	public int getProjectNumber() {
		if(projectDict==null || projectDict.isEmpty()) return 0;
		return projectDict.size();
	}
	public ProjectManager() {
		projectDict = new LinkedHashMap<String, Project> ();
		activeProjKey = null;
		workSpacePath = null;
		pseudoLibPath = null;
		qePath = null;
	}
	public ArrayList<String> getGeoName(){
		Project pj = this.getActiveProject();
		if(pj!=null) {return pj.getGeoName();}
		return null;
	}
	public Integer getActiveGeoInd(){
		Project pj = this.getActiveProject();
		if(pj!=null) {return pj.getActiveGeoInd();}
		return null;
	}
	public int getGeoListSize() {
		Project pj = this.getActiveProject();
		if(pj!=null) {return pj.getGeoListSize();}
		return 0;
	}
	public boolean isGeoActive() {
		Project pj = this.getActiveProject();
		if(pj!=null) {return pj.getGeoActive();}
		return false;//false if there is no project
	}
	public Object getObject(String fieldName, EnumStep es) {
		InputAgent ia;
		Field fd=null;
		if(EnumStep.GEO.equals(es)) {ia = getCurrentGeoAgent();}
		else {ia = getStepAgent(es);}
		if (ia==null) return null;
		try {
			switch(es) {
				case GEO:fd = InputAgentGeo.class.getField(fieldName);break;
				case SCF:fd = InputAgentScf.class.getField(fieldName);break;
				case OPT:fd = InputAgentOpt.class.getField(fieldName);break;
				case NSCF:fd = InputAgentNscf.class.getField(fieldName);break;
				case DOS:fd = InputAgentDos.class.getField(fieldName);break;
				case BOMD:fd = InputAgentMd.class.getField(fieldName);break;
				case BANDS:fd = InputAgentBands.class.getField(fieldName);break;
				case TDDFT:fd = InputAgentTddft.class.getField(fieldName);break;
				default:break;	
			}
			if(fd==null) {
				Alert alert1 = new Alert(AlertType.ERROR);
		    	alert1.setTitle("Error");
		    	alert1.setContentText("EnumStep undefined/not implemented detected in InputController!");
		    	alert1.showAndWait();
		    	return null;
			}
			return fd.get(ia);

		} catch (Exception e) {
			Alert alert1 = new Alert(AlertType.ERROR);
	    	alert1.setTitle("Error");
	    	alert1.setContentText("Cannot find field! "+e.getMessage());
	    	alert1.showAndWait();
			e.printStackTrace();
			return null;
		}
	}
	public void addGeoList(String calcFolderName, ArrayList<Atom> atomList, CellParameter cellPara, Double alat) {
		Project pj = this.getActiveProject();
		if(pj!=null) {
			pj.addGeoList(calcFolderName, atomList, cellPara, alat);
		}
	}
	public void addGeoList(String calcFolderName, InputAgentGeo iGeo) {
		Project pj = this.getActiveProject();
		if(pj!=null) {
			pj.addGeoList(calcFolderName, iGeo);
		}
	}
	public File getWorkSpaceDir() {
		if(workSpacePath==null) return null;
		File wsDir = new File(workSpacePath);
		if(wsDir.canWrite()) {return wsDir;}
		else {
			ShowAlert.showAlert(AlertType.INFORMATION, "Error", "Cannot load workspace. Please fix it.");
	    	return null;
		}
	}
	public File getProjectDir() {
		String pj = getActiveProjectName();
		if(pj!=null && !pj.isEmpty() && workSpacePath!=null) {
			File pjDir = new File(workSpacePath,pj);
			if(pjDir.exists()) {
				return pjDir;
			}
		}
		//if reached here, something must be wrong
		ShowAlert.showAlert(AlertType.INFORMATION, "Error", "Cannot load workspace/project folder. Please fix it.");
    	return null;
	}
	public File getCalculationDir() {
		File fl = getProjectDir();
		if(fl!=null && fl.canWrite()) {
			String st = getCurrentCalcName();
			if(st!=null && !st.isEmpty()) {return new File(fl,st);}
		}
		return null;
	}
	public void creatGlobalSettings() {
		File stFile = new File(DefaultFileNames.defaultSettingFile);
		try {
			stFile.createNewFile();
	    } catch (IOException e1) {
	    	ShowAlert.showAlert(AlertType.INFORMATION, "Error", "IOException while creating setting file.");
	    	e1.printStackTrace();
	    }
	}
	public String readGlobalSettings(String key) {
		String textOut=null;
		//go to current directory
		File stFile = new File(DefaultFileNames.defaultSettingFile);
		try {
			FileInputStream fis = new FileInputStream(stFile);
			InputStreamReader isr = new InputStreamReader(fis);
			BufferedReader br = new BufferedReader(isr);

			String line;
			while((line = br.readLine()) != null){
				//allText = allText + line + "\n";
				
				if(line.contains(key+"=")) {textOut=line.substring(line.lastIndexOf(key+"=") + key.length()+1);}
			}
			br.close();
			isr.close();
		} catch (FileNotFoundException e) {
			ShowAlert.showAlert(AlertType.INFORMATION, "Warning", "Probably this is your first time running QuantumVITAS because no setting "
	    			+ "file is found. The program will make one for you, and please specify your workspace folder first"
	    			+ ". Enjoy!");
	    	creatGlobalSettings();
	    	
		} catch (IOException e) {
			ShowAlert.showAlert(AlertType.INFORMATION, "Error", "Woops! IOException while reading setting file. "
	    			+ "Please delete the 'settings.ini' in the program root and restart the program.");
	    	e.printStackTrace();
		}
		return textOut;
	}
	public void writeGlobalSettings(String key, String msg) {
		//go to current directory
		File stFile = new File(DefaultFileNames.defaultSettingFile);
		for(int i=0;i<3;i++) {
			try {
				// input the (modified) file content to the StringBuffer "input"
		        BufferedReader file = new BufferedReader(new FileReader(stFile));
		        StringBuffer inputBuffer = new StringBuffer();
		        String line;
		        
		        int count = 0;
		        //find the line containing the key
		        while ((line = file.readLine()) != null) {
		            if(line.contains(key+"=")) {line=key+"="+msg;count++;}
		            inputBuffer.append(line);
		            inputBuffer.append('\n');
		        }
		        //if key not existing
		        if (count==0) {inputBuffer.append(key+"="+msg+"\n");}
		        
		        file.close();

		        // write the new string with the replaced line OVER the same file
		        FileOutputStream fileOut = new FileOutputStream(stFile);
		        
		        fileOut.write(inputBuffer.toString().getBytes());
		        fileOut.close();
		        
				break;
			} catch (FileNotFoundException e) {
				ShowAlert.showAlert(AlertType.INFORMATION, "Warning", "Setting file not found. Make a new one.");
				creatGlobalSettings();
	
			} catch (IOException e) {
				ShowAlert.showAlert(AlertType.INFORMATION, "Error", "IOException while reading setting file.");
		    	e.printStackTrace();
			}
		}
	}
	public void removeGeoList(int ind) {
		Project pj = getActiveProject();
		if(pj!=null) {
			boolean bl = pj.removeGeoList(ind);
			if(bl) {
				File wsDir = getWorkSpaceDir();
				if(wsDir==null || !wsDir.canWrite()) {return;}
				saveActiveProjectInMultipleFiles(wsDir, false,false);
				ShowAlert.showAlert(AlertType.INFORMATION, "Info", "Deleted successfully and project saved.");
			}
		}
	}
	public void saveActiveProjectInMultipleFiles() {
		File wsDir = getWorkSpaceDir();
		if(wsDir==null || !wsDir.canWrite()) {return;}
		saveActiveProjectInMultipleFiles(wsDir);
	}
	public void saveActiveProjectInMultipleFiles(File workSpaceDir) {
		//save all calculations, show success window
		saveActiveProjectInMultipleFiles(workSpaceDir, false,true);
	}
	
	public void saveActiveProjectInMultipleFiles(File workSpaceDir, boolean saveCurrentCalc, boolean showSuccess) {
		//saveCurrentCalc: true -> ONLY save current calculation. false -> save all calculations
		if(workSpaceDir==null || !workSpaceDir.canWrite()) {
			ShowAlert.showAlert(AlertType.INFORMATION, "Error", "No workspace! Cannot save...");
			return;
		}
		
		Project pj = getActiveProject();
		if(pj==null) {
			ShowAlert.showAlert(AlertType.INFORMATION, "Error", "No active project! Cannot save..");
			return;
		}
		
		File dirProj = new File(workSpaceDir,pj.getName());
		
		if(!dirProj.exists()) {//make project directory if not existing
			boolean dirCreated = dirProj.mkdir();
			if(!dirCreated) {
				ShowAlert.showAlert(AlertType.INFORMATION, "Error", "Cannot make project directory.");
		    	return;
			}
		}
		
		String msg="";
		
		//save project in one file in the project directory
		try { 
            // Saving of object in a file 
        	FileOutputStream file;
        	file = new FileOutputStream (new File(dirProj,DefaultFileNames.projSaveFile), false);
            
            ObjectOutputStream out = new ObjectOutputStream (file); 
  
            // Method for serialization of object 
            out.writeObject(pj); 
  
            out.close(); 
            file.close(); 
            
            msg+=" Project saved to "+dirProj.getAbsolutePath()+File.separator+DefaultFileNames.projSaveFile+". ";
        } 
  
        catch (IOException ex) { 
        	ShowAlert.showAlert(AlertType.INFORMATION, "Error", "IOException is caught! Cannot save general project file "+"."+ex.getMessage());
        } 
		
		//save calculation in the calculation sub-folders (just to check integrity and in case the user renamed the calculation folders)
		ArrayList<String> calcList;
		if(saveCurrentCalc) {
			if(pj.existCurrentCalc()) {
				calcList=new ArrayList<String>();
				calcList.add(pj.getActiveCalcName());//only save current calculation
			}
			else {
				ShowAlert.showAlert(AlertType.INFORMATION, "Error", "No active calculation! Cannot save... ");
	    	return;}
		}
		else {calcList= pj.getCalcList();}//save all calculations in the project
		
		if(calcList==null) {
			ShowAlert.showAlert(AlertType.INFORMATION, "Error", "Cannot access calculation list! Cannot save...");
			return;
		}
		
		for (int i=0;i<calcList.size();i++) {
			File tmpCalc = new File(dirProj,calcList.get(i));
			if(!tmpCalc.exists()) {
				if(!tmpCalc.mkdir()) {
					ShowAlert.showAlert(AlertType.INFORMATION, "Warning", "Cannot create calculation folder! Try next...");
					continue;
				}
			}
			//now either exists or freshly made. Check whether canWrite
			if(!tmpCalc.canWrite()) {
				ShowAlert.showAlert(AlertType.INFORMATION, "Warning", "No write access to the calculation folder! Try next...");
				continue;
			}
			// Serialization 
	        try { 
	            // Saving of object in a file 
	        	FileOutputStream file;
	        	file = new FileOutputStream (new File(tmpCalc,DefaultFileNames.calcSaveFile), false);
	            
	            ObjectOutputStream out = new ObjectOutputStream (file); 
	  
	            // Method for serialization of object 
	            out.writeObject(pj.getCalc(calcList.get(i))); 
	  
	            out.close(); 
	            file.close(); 
	            
	            msg+=calcList.get(i)+", ";
	        } 
	  
	        catch (IOException ex) { 
	        	ShowAlert.showAlert(AlertType.INFORMATION, "Error", "IOException is caught! Cannot save calculation "+calcList.get(i)+"."+ex.getMessage());
	        }
		}
		
		if(showSuccess) {
			String msgFinal = saveCurrentCalc ? ("Successfully saved current calculation: "+msg): ("Successfully saved current project: "+msg);
			ShowAlert.showAlert(AlertType.INFORMATION, "Success", msgFinal);
		}
    	
	}
	
	public void changeProjectName(String newName) {
		if(newName==null || newName.isEmpty() || projectDict==null || projectDict.containsKey(newName)) return;
		
		String projName = getActiveProjectName();
		if (projName==null) return;
		Project pj = projectDict.get(projName);
		pj.setName(newName);
		projectDict.remove(projName);
		projectDict.put(newName,pj);
		activeProjKey=newName;
	}
	public String loadProject(File wsDir, String projName) {
		
		if(wsDir==null || !wsDir.canRead()) {return ErrorMsg.cannotFindWorkSpaceFolder;}
		
		File projDir = new File(wsDir,projName);
		
		if(projName==null || projName.isEmpty() || !projDir.canRead()) {return ErrorMsg.cannotFindProjectFolder;}
		
		File projSaveFile = new File(projDir,DefaultFileNames.projSaveFile);
		
		String msg_all = "";
		
		if(projectDict.containsKey(projName)) {
        	//fatal error, already existing project. Will only happen when loading already loaded project. Abort
        	msg_all+= ErrorMsg.alreadyContainsProject;
        	return msg_all;
    	}
		
		if(!projSaveFile.canRead()) {
			msg_all+= ErrorMsg.cannotFindProjectSaveFile;
		}
		else {
			Project pj=null;
			// Deserialization 
	        try { 
	            // Reading the object from a file 
	            FileInputStream file1 = new FileInputStream (projSaveFile); 
	            ObjectInputStream in = new ObjectInputStream (file1); 
	  
	            // Method for deserialization of object 
	            pj = (Project)in.readObject(); 
	  
	            in.close(); 
	            file1.close(); 
	            
	            if(pj==null) {msg_all+= "Project read from file is null";}
	            else {
		            if(!projName.equals(pj.getName())) {
		            	//project name different than the folder name. Use the folder name
		            	msg_all+=("Rename project name in the saved file from '"+pj.getName()+"' to '"+projName+"'. ");
		            	pj.setName(projName);
		            	
		            	//update the .proj file
		            	FileOutputStream file2;
		            	file2 = new FileOutputStream (projSaveFile, false);
		                ObjectOutputStream out = new ObjectOutputStream (file2); 
		      
		                // Method for serialization of object 
		                out.writeObject(pj); 
		      
		                out.close(); 
		                file1.close(); 
		                
		                msg_all+="Project saved to "+projSaveFile.getAbsolutePath()+". ";
		            }
		            
		        	
		            projectDict.put(pj.getName(), pj);
					activeProjKey = pj.getName();
	            }
	        } 
	        catch (IOException ex) { 
		    	msg_all+= "IOException.";
	        } 
	        catch (ClassNotFoundException ex) { 
		    	msg_all+= "ClassNotFoundException.";
	        }
		}
		
		
		if(!projName.equals(activeProjKey)) {
			msg_all+="\n";
			String msg2 = addProject(projName);
			if(msg2==null) {msg_all+=ErrorMsg.createProject;}//successfully created project, continue
			else {msg_all+=msg2;return msg_all;}//fatal error, cannot add new project, stop here. 
			//Above: since projName will not be empty, error will only happen when ErrorMsg.alreadyContainsProject, which has already been taken care of before
		}
		else {
			//everything fine
			msg_all+="Project save file successfully loaded.";
		}
		
		msg_all+="\n";
		String msg3="";
		int calcCount=0;
		//load calculations regardless
		//*************need to take care of the geo part if newly created project
		File[] directories = projDir.listFiles(File::isDirectory);
		CalculationClass clc;
		Project pjNew = getActiveProject();
		if(pjNew!=null) {
			for (File temp : directories) {
				calcCount++;
				String calcName = temp.getName();
				try { 
		            // Reading the object from a file 
					File fl = new File(new File(projDir,calcName),DefaultFileNames.calcSaveFile);
					if (calcName==null || calcName.isEmpty() || !fl.canRead()) {msg3+="Cannot load calculation in "+calcName+". ";continue;}
		            FileInputStream file = new FileInputStream (fl); 
		            ObjectInputStream in = new ObjectInputStream (file); 
		  
		            // Method for deserialization of object 
		            clc = (CalculationClass)in.readObject(); 
		  
		            in.close(); 
		            file.close(); 
		            if(clc==null) {msg3+="Cannot load calculation in "+calcName+". ";continue;}
		            
		            if(msg_all.contains(ErrorMsg.createProject)) {//new project, but load existing calculations
		            	clc.setGeoInd(0);//set geometry to 0 because it always exists
		            }
		            
		            pjNew.addCalculation(calcName, clc);
		        } 
		        catch (IOException ex) { 
		        	msg3+="IOException is caught! Cannot load calculation file "+calcName+". ";
		        } 
		        catch (ClassNotFoundException ex) { 
		        	msg3+="ClassNotFoundException is caught! Cannot find calculation class "+calcName+". ";
		        }
			}
		}
		if(calcCount==0) {
			msg_all+="No calculation to be loaded. ";
		}
		else {
			if(msg3.isEmpty()) {
				msg_all+="All calculations successfully loaded. ";
				if(msg_all.contains(ErrorMsg.createProject)) {
					msg_all+="Set active geometry of all calculations to the first geometry.";
				}
			}
			else {msg_all+=msg3;}
		}
		
		if (msg_all.isEmpty()) {return null;}
		else {return msg_all;}
		
		
	}
	public void updateViewerPlot() {
		Project pj = getActiveProject();
		if (pj==null) return;
		pj.updateViewerPlot();
	}
	public boolean existProject(String nameProject) {
		if (nameProject==null || nameProject.isEmpty() || projectDict==null || projectDict.isEmpty()) {return false;}
		return projectDict.containsKey(nameProject);
	}
	public String checkProjectName(String nameProject) {
		if (nameProject==null || nameProject.isEmpty())
			return "Empty project name!";
		else if (projectDict.containsKey(nameProject)){
			return ErrorMsg.alreadyContainsProject;
		}
		else {
			return null;
		}	
	}
	
	public boolean containsProject(String nameProject) {
		if (nameProject==null || nameProject.isEmpty() || projectDict==null)
			return false;
		else return projectDict.containsKey(nameProject);
	}
	public String addProject(String nameProject) {
		String tmp = checkProjectName(nameProject);
		if (tmp!=null) return tmp;
		else {
			projectDict.put(nameProject, new Project(nameProject));
			activeProjKey = nameProject;
			return null;
		}	
	}
	public void setStepAsDefault(EnumStep es) {
		projectDict.get(activeProjKey).setProjectDefault(es);//no cloning, just reference
	}
	public Boolean isDefault() {
		if (!existCurrentProject()) return false;
		else return projectDict.get(activeProjKey).isDefault();
	}
	public void loadStepFromDefault(EnumStep es) {
		if (!existCurrentProject()) return;
		InputAgent ia = projectDict.get(activeProjKey).getProjectDefault(es);//already cloned in getProjectDefault()
		setStepAgent(es,ia);
	}
	public void addCalculation(String nameProject, EnumCalc ec) {//use default naming
		if (nameProject==null || ec==null || nameProject.isEmpty()) return;
		if (!projectDict.containsKey(nameProject)) addProject(nameProject);//continue to add calc
		projectDict.get(nameProject).addCalculation(ec);
	}
	public void addCalculation(String nameProject, String calcName, EnumCalc ec) {//use custom naming
		if (nameProject==null || ec==null || nameProject.isEmpty()) return;
		if (!projectDict.containsKey(nameProject)) addProject(nameProject);//continue to add calc
		projectDict.get(nameProject).addCalculation(calcName,ec);
	}
	public void addCalcToActiveProj(EnumCalc ec) {//use default naming
		if (activeProjKey==null|| ec==null || activeProjKey.isEmpty() || ! projectDict.containsKey(activeProjKey)) return;
		projectDict.get(activeProjKey).addCalculation(ec);
	}
	public void addCalcToActiveProj(String calcName, EnumCalc ec) {//use custom naming
		if (activeProjKey==null|| ec==null || activeProjKey.isEmpty() || ! projectDict.containsKey(activeProjKey)) return;
		projectDict.get(activeProjKey).addCalculation(calcName, ec);
	}
	public void setActiveProject(String nameProject) {
		if (nameProject==null || nameProject.isEmpty() || projectDict == null)
			activeProjKey = null;
		else if (projectDict.containsKey(nameProject)){
			activeProjKey = nameProject;
		}
	}
	public void setActiveCalculation(String ec) {
		if (existCurrentProject()) {
			projectDict.get(activeProjKey).setActiveCalcName(ec);
		}
	}
	public void setGeoActive(Boolean bl) {
		if (existCurrentProject()) {
			projectDict.get(activeProjKey).setGeoActive(bl);
		}
	}
	public Boolean existCurrentProject() {
		if (activeProjKey==null || activeProjKey.isEmpty() || projectDict==null || ! projectDict.containsKey(activeProjKey)) {
			return false;
		}
		else {
			return true;
		}
	}
	public Boolean existCurrentCalc() {
		if (!existCurrentProject()) return false;
		return projectDict.get(activeProjKey).existCurrentCalc();
	}
	public Boolean existCalcInCurrentProject(String ec) {
		if (!existCurrentProject()) return false;
		return projectDict.get(activeProjKey).existCalc(ec);
	}
	public Boolean isCurrentCalc(String ec) {
		if (!existCurrentCalc()) return false;//false, not null!
		return java.util.Objects.equals(projectDict.get(activeProjKey).getActiveCalcName(),ec);
	}
	public Boolean existCurrentStep(EnumStep es) {
		if (!existCurrentCalc()) return false;
		return projectDict.get(activeProjKey).getActiveCalc().existStep(es);
	}
	public String getCurrentCalcName() {
		if (!existCurrentCalc()) return null;
		return projectDict.get(activeProjKey).getActiveCalcName();
	}
	public EnumCalc getCurrentCalcType() {
		if (!existCurrentCalc()) return null;
		return projectDict.get(activeProjKey).getActiveCalc().getCalcType();
	}
	public ArrayList<String> getCurrentCalcList(){
		if (!existCurrentProject()) return new ArrayList<String>(); //return an empty list
		return projectDict.get(activeProjKey).getCalcList();
	}
	public InputAgent getStepAgent(EnumStep es) {
		if (!existCurrentCalc()) return null;
		return projectDict.get(activeProjKey).getActiveCalc().getAgent(es);
	}
	public void setStepAgent(EnumStep es,InputAgent ia) {
		if (!existCurrentCalc()) return;
		else projectDict.get(activeProjKey).getActiveCalc().setAgent(es,ia);
	}
	public InputAgentGeo getCurrentGeoAgent() {
		if (!existCurrentProject()) return null;
		return projectDict.get(activeProjKey).getAgentGeo();
	}
	public void setCurrentGeoInd(int ind) {
		if (!existCurrentProject()) return;
		projectDict.get(activeProjKey).setActiveGeoInd(ind);
	}
	public String removeProject(String nameProject) {
		if (nameProject==null || nameProject.isEmpty())
			return "Empty project name!";
		else if (projectDict.containsKey(nameProject)){
			projectDict.remove(nameProject);
			if (nameProject.equals(activeProjKey)){
				activeProjKey = getNextKey(nameProject);
			}
			return null;
		}
		else {
			return "No project named "+nameProject;
		}
	}
	private String getNextKey(String nameProject) {
		boolean flag = false;
		if (!projectDict.isEmpty()){
			for (String key : projectDict.keySet()) {
				if (java.util.Objects.equals(key,nameProject)) {
					flag = true;
					continue;
				}
				if (flag) {
					return key;
				}
			}
		}
		return null;
	}
	public String getActiveProjectName() {
		if (projectDict==null || activeProjKey == null)  return null;
		if (projectDict.containsKey(activeProjKey)) 
		{
			return activeProjKey;
		}
		else {
			return null;
		}
	}
	public Project getActiveProject() {
		if (projectDict==null || activeProjKey == null || activeProjKey.isEmpty())  return null;
		if (projectDict.containsKey(activeProjKey)) 
		{
			Project pj = projectDict.get(activeProjKey);
			return pj;
		}
		else {
			return null;
		}
	}
	public EnumCalc getCalcType(String calcName) {
		if(calcName==null || calcName.isEmpty()) return null;
		Project pj = getActiveProject();
		if(pj==null) return null;
		return pj.getCalcType(calcName);
	}
	public QeInput getProjectCalcInp(String proj, String calc, EnumStep indInp) {
		if (projectDict==null || activeProjKey == null || calc == null || indInp == null || proj == null|| 
				proj.isEmpty() )  return null;
		
		if (!projectDict.containsKey(proj)) return null;
		
		Project pj = projectDict.get(proj);
		if (pj==null) return null;
		
		CalculationClass cc =  pj.getCalc(calc);
		if (cc==null) return null;
		
		QeInput qi = cc.getQeInput(indInp);
		if (qi==null) return null;
		
		return qi;
	}
	public QeInput getActiveProjectCalcInp(String calc, EnumStep indInp) {
		if (projectDict==null || activeProjKey == null || calc == null || indInp == null)  return null;
		
		if (!projectDict.containsKey(activeProjKey)) return null;
		
		Project pj = projectDict.get(activeProjKey);
		if (pj==null) return null;
		
		CalculationClass cc =  pj.getCalc(calc);
		if (cc==null) return null;
		
		QeInput qi = cc.getQeInput(indInp);
		if (qi==null) return null;
		
		return qi;
	}
	public ArrayList<ContainerInputString> genInputFromAgent() {
		Project pj =  getActiveProject();
		if(pj==null) {
			ShowAlert.showAlert(AlertType.INFORMATION, "No project!", "No project!");
	    	return null;
		}
		else return pj.genInputFromAgent();
	}
	public String getPseudoLibPath() {
		return pseudoLibPath;
	}
	public void setPseudoLibPath(String pseudoLibPath) {
		PseudoPotential.setRootFolder(new File(pseudoLibPath));
		this.pseudoLibPath = pseudoLibPath;
	}
	
	
}
