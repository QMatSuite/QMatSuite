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
import java.util.ArrayList;
import java.util.LinkedHashMap;
import com.consts.Constants.EnumCalc;
import com.consts.Constants.EnumStep;
import com.consts.DefaultFileNames;
import com.error.ErrorMsg;

import agent.InputAgent;
import agent.InputAgentGeo;
import input.ContainerInputString;
import input.QeInput;
import javafx.scene.control.Alert;
import javafx.scene.control.Alert.AlertType;

public class ProjectManager {
	public String workSpacePath;
	public String pseudoLibPath;
	public String qePath;
	private LinkedHashMap<String, Project> projectDict;
	private String activeProjKey;
	
	public ProjectManager() {
		projectDict = new LinkedHashMap<String, Project> ();
		activeProjKey = null;
		workSpacePath = null;
		pseudoLibPath = null;
		qePath = null;
	}
	public File getWorkSpaceDir() {
		File wsDir = new File(workSpacePath);
		if(wsDir!=null && wsDir.canWrite()) {return wsDir;}
		else {
			Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setTitle("Error");
	    	alert1.setContentText("Cannot load workspace. Please fix it.");
	    	alert1.showAndWait();
	    	return null;
		}
	}
	public File getProjectDir() {
		String pj = getActiveProjectName();
		if(pj!=null && !pj.isEmpty() && workSpacePath!=null) {
			File pjDir = new File(workSpacePath,pj);
			if(pjDir!=null && pjDir.exists()) {
				return pjDir;
			}
		}
		//if reached here, something must be wrong
		Alert alert1 = new Alert(AlertType.INFORMATION);
    	alert1.setTitle("Error");
    	alert1.setContentText("Cannot load workspace/project folder. Please fix it.");
    	alert1.showAndWait();
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
	    	Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setTitle("Error");
	    	alert1.setContentText("IOException while creating setting file.");
	    	alert1.showAndWait();
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
		} catch (FileNotFoundException e) {
			Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setTitle("Warning");
	    	alert1.setContentText("Setting file not found. Make a new one.");
	    	alert1.showAndWait();
	    	
	    	creatGlobalSettings();
	    	
		} catch (IOException e) {
			Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setTitle("Error");
	    	alert1.setContentText("IOException while reading setting file.");
	    	alert1.showAndWait();
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
				Alert alert1 = new Alert(AlertType.INFORMATION);
		    	alert1.setTitle("Warning");
		    	alert1.setContentText("Setting file not found. Make a new one.");
		    	alert1.showAndWait();
		    	
				creatGlobalSettings();
	
			} catch (IOException e) {
				Alert alert1 = new Alert(AlertType.INFORMATION);
		    	alert1.setTitle("Error");
		    	alert1.setContentText("IOException while reading setting file.");
		    	alert1.showAndWait();
			}
		}
	}
	public void saveActiveProjectInMultipleFiles(File workSpaceDir) {
		//save all calculations, show success window
		saveActiveProjectInMultipleFiles(workSpaceDir, false,true);
	}
	public void saveActiveProjectInMultipleFiles(File workSpaceDir, boolean saveCurrentCalc, boolean showSuccess) {
		if(workSpaceDir==null || !workSpaceDir.canWrite()) {
			Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setTitle("Error");
	    	alert1.setContentText("No workspace! Cannot save...");
	    	alert1.showAndWait();
			return;
		}
		
		Project pj = getActiveProject();
		if(pj==null) {
			Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setTitle("Error");
	    	alert1.setContentText("No active project! Cannot save...");
	    	alert1.showAndWait();
			return;
		}
		
		File dirProj = new File(workSpaceDir,pj.getName());
		
		if(dirProj!=null && !dirProj.exists()) {//make project directory if not existing
			boolean dirCreated = dirProj.mkdir();
			if(!dirCreated) {
				Alert alert1 = new Alert(AlertType.INFORMATION);
		    	alert1.setTitle("Error");
		    	alert1.setContentText("Cannot make project directory.");
		    	alert1.showAndWait();
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
			Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setTitle("Error");
	    	alert1.setContentText("IOException is caught! Cannot save general project file "+"."+ex.getMessage());
	    	alert1.showAndWait();
        } 
		
		//save calculation in the calculation sub-folders (just to check integrity and in case the user renamed the calculation folders)
		ArrayList<String> calcList;
		if(saveCurrentCalc) {
			if(pj.existCurrentCalc()) {
				calcList=new ArrayList<String>();
				calcList.add(pj.getActiveCalcName());//only save current calculation
			}
			else {Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setTitle("Error");
	    	alert1.setContentText("No active calculation! Cannot save... ");
	    	alert1.showAndWait();
	    	return;}
		}
		else {calcList= pj.getCalcList();}//save all calculations in the project
		
		if(calcList==null) {
			Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setTitle("Error");
	    	alert1.setContentText("Cannot access calculation list! Cannot save...");
	    	alert1.showAndWait();
			return;
		}
		
		for (int i=0;i<calcList.size();i++) {
			File tmpCalc = new File(dirProj,calcList.get(i));
			if(!tmpCalc.exists()) {
				if(!tmpCalc.mkdir()) {
					Alert alert1 = new Alert(AlertType.INFORMATION);
			    	alert1.setTitle("Warning");
			    	alert1.setContentText("Cannot create calculation folder! Try next...");
			    	alert1.showAndWait();
					continue;
				}
			}
			//now either exists or freshly made. Check whether canWrite
			if(!tmpCalc.canWrite()) {
				Alert alert1 = new Alert(AlertType.INFORMATION);
		    	alert1.setTitle("Warning");
		    	alert1.setContentText("No write access to the calculation folder! Try next...");
		    	alert1.showAndWait();
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
				Alert alert1 = new Alert(AlertType.INFORMATION);
		    	alert1.setTitle("Error");
		    	alert1.setContentText("IOException is caught! Cannot save calculation "+calcList.get(i)+"."+ex.getMessage());
		    	alert1.showAndWait();
	        }
		}
		
		if(showSuccess) {
			Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setTitle("Success");
	    	if (saveCurrentCalc) {alert1.setContentText("Successfully saved current calculation: "+msg);}
	    	else {alert1.setContentText("Successfully saved current project: "+msg);}
	    	alert1.showAndWait();
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
		
		if(projName==null || projName.isEmpty() || projDir==null || !projDir.canRead()) {return ErrorMsg.cannotFindProjectFolder;}
		
		File projSaveFile = new File(projDir,DefaultFileNames.projSaveFile);
		
		String msg_all = "";
		
		if(projectDict.containsKey(projName)) {
        	//fatal error, already existing project. Will only happen when loading already loaded project. Abort
        	msg_all+= ErrorMsg.alreadyContainsProject;
        	return msg_all;
    	}
		
		if(projSaveFile==null || !projSaveFile.canRead()) {
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
		calculationClass clc;
		Project pjNew = getActiveProject();
		if(pjNew!=null) {
			for (File temp : directories) {
				calcCount++;
				String calcName = temp.getName();
				try { 
		            // Reading the object from a file 
					File fl = new File(new File(projDir,calcName),DefaultFileNames.calcSaveFile);
					if (calcName==null || calcName.isEmpty() || fl==null || !fl.canRead()) {msg3+="Cannot load calculation in "+calcName+". ";continue;}
		            FileInputStream file = new FileInputStream (fl); 
		            ObjectInputStream in = new ObjectInputStream (file); 
		  
		            // Method for deserialization of object 
		            clc = (calculationClass)in.readObject(); 
		  
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
		else {
			
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
		return projectDict.get(activeProjKey).getActiveCalcName()==ec;
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
			if (activeProjKey==nameProject){
				activeProjKey = getNextKey(nameProject);
			}
			return null;
		}
		else {
			return "No project named "+nameProject;
		}
	}
	private String getNextKey(String nameProject) {
		Boolean flag = false;
		if (!projectDict.isEmpty()){
			for (String key : projectDict.keySet()) {
				if (key == nameProject) {
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
		
		calculationClass cc =  pj.getCalc(calc);
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
		
		calculationClass cc =  pj.getCalc(calc);
		if (cc==null) return null;
		
		QeInput qi = cc.getQeInput(indInp);
		if (qi==null) return null;
		
		return qi;
	}
	public ArrayList<ContainerInputString> genInputFromAgent() {
		Project pj =  getActiveProject();
		if(pj==null) {
			Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setHeaderText("No project!");
	    	alert1.setContentText("No project!");
	    	alert1.showAndWait();
	    	return null;
		}
		else return pj.genInputFromAgent();
	}
	
}
