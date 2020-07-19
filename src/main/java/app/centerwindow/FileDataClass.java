/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive 
 *     Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or any 
 *     later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package app.centerwindow;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Scanner;
import com.consts.ChemicalElements;
import com.consts.Constants.EnumFileCategory;
import com.consts.Constants.EnumStep;
import com.consts.Constants.EnumUnitCellAngle;
import com.consts.Constants.EnumUnitCellLength;
import com.consts.Constants.EnumUnitCellParameter;
import com.consts.PhysicalConstants;
import com.error.ShowAlert;
import com.programconst.ProgrammingConsts;
import agent.InputAgentGeo;
import app.input.CellParameter;
import app.input.geo.Atom;
import javafx.geometry.Point3D;
import javafx.scene.control.Alert.AlertType;

public class FileDataClass {
	private ArrayList<ArrayList<Double>> energyArray;//Ry
	private ArrayList<Double> fermiLevel;//eV
	private ArrayList<Double> homoLevel;//eV
	private ArrayList<Double> totalForce;//Ry/Bohr
	private ArrayList<Double> totalPressure;//kBar
	
	private ArrayList<ArrayList<Double>> totalMag;//Bohr mag/cell
	
	
	private ArrayList<ArrayList<Double>> absoluteMag;//Bohr mag/cell
	private ArrayList<ArrayList<Double>> dosArray;
	private ArrayList<String> dosHeader;
	private ArrayList<ArrayList<ArrayList<Double>>> bandsDatArray;
	private ArrayList<Double> bandsHighSymmetryKXCoor;
	private ArrayList<String> bandsHighSymmetryK;
	
	private ArrayList<ArrayList<Double>> tddftArray;
	private ArrayList<String> tddftHeader;
	
	private ArrayList<ArrayList<Double>> dataMd;//4*n dimension
	
	public Double fermiDos=null;
	public EnumFileCategory fileCategory=null;
	
	//initial parameters
	private Double alat = null;
	private InputAgentGeo iGeoTemp;
	//movement
	private ArrayList<ArrayList<Atom>> atomicPositions;
	private boolean finalPosition=false;
	private ArrayList<CellParameter> cellParameter;
	private String errorMessage = "";
	
	public int nstep=1;
	public boolean isJobStart = false;
	public boolean isJobDone=false;
	public boolean hasScf=false;//true when there exist scf steps inside the output file. Not necessary means that it is a scf calculation
	public boolean hasScfFinished=false;
	public boolean isMD=false;
	public boolean isMDFinished=false;
	public boolean isOpt=false;
	public boolean isOptFinished=false;
	public boolean isNscf=false;
	public boolean isNscfFinished=false;
	public boolean isDos=false;
	public boolean isDosFinished=false;
	public boolean isPwBands = false;
	public boolean isBandsPP = false;
	public boolean isTddftTurbo = false;
	public boolean isTddftSpectrum = false;
	
	
	//will be true when one scf just finished. Will be set back to false when one new mag is read
	private boolean flagScfFinishedForTotalMag=false;
	private boolean flagScfFinishedForAbsMag=false;
	
	public FileDataClass() {
		energyArray = new ArrayList<ArrayList<Double>>();
		fermiLevel = new ArrayList<Double>();
		homoLevel = new ArrayList<Double>();
		totalForce = new ArrayList<Double>();
		totalPressure = new ArrayList<Double>();
		
		totalMag = new ArrayList<ArrayList<Double>>();
		absoluteMag = new ArrayList<ArrayList<Double>>();
		dosArray = new ArrayList<ArrayList<Double>>();
		bandsDatArray = new ArrayList<ArrayList<ArrayList<Double>>>();
		bandsHighSymmetryKXCoor = new ArrayList<Double>();
		bandsHighSymmetryK = new ArrayList<String>();
		dosHeader = new ArrayList<String>();
		atomicPositions = new ArrayList<ArrayList<Atom>>();
		cellParameter = new ArrayList<CellParameter>();
		tddftArray = new ArrayList<ArrayList<Double>>();
		tddftHeader = new ArrayList<String>();
		iGeoTemp = new InputAgentGeo();
				
		dataMd = new ArrayList<ArrayList<Double>>();//DO NOT CLEAR dataMd itself!
		dataMd.add(new ArrayList<Double>());//time in ps
		dataMd.add(new ArrayList<Double>());//Ekin
		dataMd.add(new ArrayList<Double>());//temperature
		dataMd.add(new ArrayList<Double>());//total energy (should be constant)
	}
	public ArrayList<ArrayList<ArrayList<Double>>> getBandsDatArray(){
		return this.bandsDatArray;
	}
	public void clearAll() {
		for(ArrayList<Double> ard:energyArray) {
			if(ard!=null) {ard.clear();}
		}
		for(ArrayList<Double> ard:totalMag) {
			if(ard!=null) {ard.clear();}
		}
		for(ArrayList<Double> ard:absoluteMag) {
			if(ard!=null) {ard.clear();}
		}
		for(ArrayList<Double> ard:dosArray) {
			if(ard!=null) {ard.clear();}
		}
		for(ArrayList<Double> ard:tddftArray) {
			if(ard!=null) {ard.clear();}
		}
		for(ArrayList<ArrayList<Double>> ard:bandsDatArray) {
			if(ard!=null) {
				for(ArrayList<Double> ard1:ard) {
					if(ard1!=null) {ard1.clear();}
				}
				ard.clear();
			}
		}
		for(ArrayList<Atom> ard:atomicPositions) {
			if(ard!=null) {ard.clear();}
		}
		for(ArrayList<Double> arr:dataMd) {
			arr.clear();//DO NOT CLEAR dataMd itself!
		}
		energyArray.clear();
		fermiLevel.clear();
		homoLevel.clear();
		totalForce.clear();
		totalPressure.clear();
		
		totalMag.clear();
		absoluteMag.clear();
		dosArray.clear();
		dosHeader.clear();
		bandsDatArray.clear();
		bandsHighSymmetryK.clear();
		bandsHighSymmetryKXCoor.clear();
		tddftArray.clear();
		tddftHeader.clear();
		errorMessage = "";
		
		//not necessary, because atom positions not encoded there. 
		//Further, DO NOT DO IT otherwise the workscene3d will not work for the in/out
		//iGeoTemp = new InputAgentGeo();
		
		atomicPositions.clear();
		alat = null;
		cellParameter.clear();
		finalPosition=false;
		
		nstep=1;fermiDos=null;
		isJobDone=false;
		isJobStart = false;
		hasScf=false;hasScfFinished=false;isMD=false;isMDFinished=false;isOpt=false;isOptFinished=false;
		isNscf=false;isNscfFinished=false;isDos=false;isDosFinished=false;
		isPwBands = false;isBandsPP = false;isTddftTurbo = false;isTddftSpectrum=false;
		flagScfFinishedForTotalMag=false;
		flagScfFinishedForAbsMag=false;
	}
	public InputAgentGeo getGeoAgent() {
		return this.iGeoTemp;
	}
	public ArrayList<Atom> getFinalAtomicPositions(){
		if(atomicPositions==null || atomicPositions.isEmpty() || !finalPosition) {return null;}
		return atomicPositions.get(atomicPositions.size()-1);
	}
	public CellParameter getFinalCellParameter(){
		if(cellParameter==null || cellParameter.isEmpty() || !finalPosition) {return null;}
		return cellParameter.get(cellParameter.size()-1);
	}
	public Double getAlat(){
		return alat;
		
	}
	public boolean loadBands(File gnuDatFile) {
		if(!gnuDatFile.canRead()) {
			return false;
		}
		this.clearAll();
		
		File scfOutFile = new File(gnuDatFile.getParentFile(),EnumStep.SCF.toString()+ProgrammingConsts.stdoutExtension);
		File bandsPpOutFile = new File(gnuDatFile.getParentFile(),EnumStep.BANDSPP.toString()+ProgrammingConsts.stdoutExtension);
		try {
			//scf out file to extract Fermi energy
			if(scfOutFile.canRead()) {
			    Scanner sc1 = new Scanner(scfOutFile); 
			  
			    String strTmp;
			    
			    while (sc1.hasNextLine()) {
	
			    	strTmp = sc1.nextLine();
			    	
			    	if(strTmp==null || strTmp.isEmpty()) continue;
			    	
			    	if(strTmp.toLowerCase().contains("fermi energy")) {
			    		String[] splitted = strTmp.trim().split("\\s+");//split the string by whitespaces
						try {
			    			Double dbTmp =  Double.valueOf(splitted[4]);
			    			if(dbTmp!=null) {fermiDos = dbTmp;}
			    		}catch(Exception e) {
			    			e.printStackTrace();
			    		}
			    	}
	
		    	}
			    
			    sc1.close();
			}

		    //load .gnu file
		    Scanner sc2 = new Scanner(gnuDatFile); 
		    String strTmp;
		    bandsDatArray.add(new ArrayList<ArrayList<Double>>());
		    
		    while (sc2.hasNextLine()) {

		    	strTmp = sc2.nextLine();
		    	
		    	if(strTmp==null || strTmp.trim().isEmpty()) {
		    		if(!bandsDatArray.get(bandsDatArray.size()-1).isEmpty()) {
		    			bandsDatArray.add(new ArrayList<ArrayList<Double>>());
		    		}
		    		continue;
		    	}
		    	addDoubleRow(strTmp,bandsDatArray.get(bandsDatArray.size()-1));
	    	}
		    sc2.close();
		    
		    //load bandspp.out file to get high symmetry points
		    if(bandsPpOutFile.canRead()) {
			    Scanner sc3 = new Scanner(bandsPpOutFile); 
			    
			    while (sc3.hasNextLine()) {
			    	strTmp = sc3.nextLine();

			    	if(strTmp==null || strTmp.trim().isEmpty()) {
			    		continue;
			    	}
			    	if(strTmp.contains("high-symmetry point")) {
			    		int ind1 = strTmp.indexOf(":");
			    		int ind2 = strTmp.indexOf("x coordinate");
			    		if(ind1==-1 || ind2==-1) {continue;}
			    		bandsHighSymmetryK.add(strTmp.substring(ind1+1,ind2).trim());
			    		String[] splitted = strTmp.trim().split("\\s+");//split the string by whitespaces
						try {
			    			Double dbTmp =  Double.valueOf(splitted[splitted.length-1]);
			    			if(dbTmp!=null) {bandsHighSymmetryKXCoor.add(dbTmp);}
			    		}catch(Exception e) {
			    			e.printStackTrace();
			    		}
			    	}
		    	}
			    sc3.close();
			    if(bandsHighSymmetryK.size()!=bandsHighSymmetryKXCoor.size()) {
			    	ShowAlert.showAlert(AlertType.INFORMATION, "Warning", 
							"bandsHighSymmetryK and bandsHighSymmetryKXCoor having different sizes.");
			    	//so that we can assume they always have same size later in the program
			    }
		    }
		    
		} catch (IOException e) {
			e.printStackTrace();
			return false;
		}
		return true;
	}
	public void addDoubleRow(String line, ArrayList<ArrayList<Double>> arrList) {
		ArrayList<Double> al = new ArrayList<Double>();
		String[] splitted = line.trim().split("\\s+");//split the string by whitespaces
		try {
			for(int i=0;i<splitted.length;i++) {
				al.add(Double.valueOf(splitted[i]));
			}	
			arrList.add(al);
		}
		catch(Exception e) {
			e.printStackTrace();
		}
	}
	private void setFermi(String strLine) {
		if(strLine==null) {return;}
		if(strLine.toLowerCase().contains("fermi energy")) {
			String[] splitted = strLine.trim().split("\\s+");//split the string by whitespaces
			try {
    			Double dbTmp =  Double.valueOf(splitted[4]);
    			if(dbTmp!=null) {this.setFermi(dbTmp);}
    		}catch(Exception e) {
    			e.printStackTrace();
    		}
		}
	}
	public boolean loadDOS(File inoutFiles) {//return false when error
		
		try {
			this.clearAll();
			
		    Scanner sc = new Scanner(inoutFiles); 
		  
		    String strTmp;
		    
		    boolean flagHeader=false;
		    
		    while (sc.hasNextLine()) {

		    	strTmp = sc.nextLine();
		    	
		    	if(strTmp==null || strTmp.isEmpty()) continue;
		    	if(strTmp.contains("#")||strTmp.contains("=")) {
		    		flagHeader=true;
		    		this.addDosHeader(strTmp);
		    		continue;
		    	}
		    	if(flagHeader) {
		    		this.addDoubleRow(strTmp,dosArray);
		    	}
	    	}
		    
		    sc.close();
		    
		} catch (IOException e) {
			e.printStackTrace();
			return false;
		}
		return true;
	}
	public boolean loadTddft(File inoutFiles) {
		try {
			this.clearAll();
			
		    Scanner sc = new Scanner(inoutFiles); 
		  
		    String strTmp;
		    
		    boolean flagHeader=false;
		    
		    while (sc.hasNextLine()) {

		    	strTmp = sc.nextLine();
		    	
		    	if(strTmp==null || strTmp.isEmpty()) continue;
		    	if(strTmp.contains("#")) {
		    		flagHeader=true;
		    		this.addTddftHeader(strTmp);
		    		continue;
		    	}
		    	if(flagHeader) {
		    		this.addDoubleRow(strTmp,tddftArray);
		    	}
	    	}
		    
		    sc.close();
		    
		} catch (IOException e) {
			e.printStackTrace();
			return false;
		}
		return true;
	}
	private void setDataMd(int indexMd, String strLine, int stepNum) {
		//indexMd:
		//0, time in ps
		//1, Ekin in Ry
		//2, temperature in K
		//3, total energy (should be constant) in Ry
		if(strLine==null || strLine.trim().isEmpty() || stepNum<0) {return;}
		Double valTmp = null;
		final int indexOfNumber;
		if(indexMd==0) {
			indexOfNumber = 2;
		}
		else if(indexMd==1) {
			indexOfNumber = 4;
		}
		else if(indexMd==2) {
			indexOfNumber = 2;
		}
		else if(indexMd==3) {
			indexOfNumber = 5;
		}
		else {
			indexOfNumber = -1;
			return;
		}
		
		String[] splitted = strLine.trim().split("\\s+");//split the string by whitespaces
		try {
			valTmp = Double.valueOf(splitted[indexOfNumber]);
			if(valTmp==null) {valTmp = Double.NaN;}
		}catch(Exception e) {
			valTmp = Double.NaN;
		}
		
		int sz = this.dataMd.get(indexMd).size();
		if(stepNum < sz) {this.dataMd.get(indexMd).set(stepNum, valTmp);}
		else if(stepNum == sz) {this.dataMd.get(indexMd).add(valTmp);}
		else {
			//the following should not happen unless the output file is corrupted.
			for(int i=sz;i<stepNum;i++) {
				this.dataMd.get(indexMd).add(Double.NaN);
			}
			//after this, this.dataMd.get(indexMd).size()==stepNum
			this.dataMd.get(indexMd).add(valTmp);
		}
	}
	public String loadStdOut(File inoutFiles) {//return non empty string when error. Return "" (empty string) when no error

		this.clearAll();
		boolean recordAtomicPos = false;
		boolean recordCellPara = false;
		
		this.iGeoTemp.unitCellLength = EnumUnitCellLength.bohr;
		this.iGeoTemp.unitCellAngle = EnumUnitCellAngle.degree;
		this.iGeoTemp.unitCellParameter = EnumUnitCellParameter.alat;
		
		this.addNewAtomPosition();//for initial positions
		this.addNewCell();//for initial parameters
		
		boolean startCalc = false;
		
		try {
		    Scanner sc = new Scanner(inoutFiles); 
		  
		    String strTmp;
		    String argCache=null;//caches the argument like ATOMIC_POSITIONS (crystal)
		    
		    int lineCount=0;
		    int iterationMD = -1;
		    int errorLineNum = 0;
		    boolean flagError = false;
		    
		    while (sc.hasNextLine()) {
		    	lineCount++;
		    	strTmp = sc.nextLine();
		    	//total energy
		    	if(strTmp==null || strTmp.isEmpty()) continue;
		    	
		    	String lowerCaseStr = strTmp.toLowerCase();
		    	if(recordAtomicPos) {
		    		recordAtomicPos = this.addAtomicPosition(strTmp,argCache);
		    	}
		    	if(recordCellPara) {
		    		recordCellPara = this.addCellParameter(strTmp,argCache);
		    	}
		    	
		    	if(strTmp.contains("plot nbnd")) {
		    		this.isPwBands = true;
		    	}
		    	if(strTmp.contains("Program BANDS")) {
		    		this.isBandsPP = true;
		    	}
		    	if(strTmp.contains("Program turboTDDFT")) {
		    		this.isTddftTurbo = true;
		    	}
		    	if(strTmp.contains("Program TDDFPT_PP")) {
		    		this.isTddftSpectrum = true;
		    	}
		    	if(strTmp.contains("starts")) {
		    		this.isJobStart = true;
		    	}
		    	if(strTmp.contains("tau(") && !startCalc) {
		    		this.parseInitialAtomPos(strTmp);
		    	}
		    	if(strTmp.trim().startsWith("a(") && strTmp.contains(") = (") && !startCalc) {
		    		this.parseInitialCellPara(strTmp);
		    	}
		    	if(this.isMD) {
			    	if(strTmp.contains("Entering Dynamics") && strTmp.contains("iteration")) {
			    		iterationMD++;
			    	}
			    	if(strTmp.contains("time") && strTmp.contains("pico-seconds") && strTmp.contains("=")) {
			    		setDataMd(0,strTmp,iterationMD);
			    	}
			    	if(strTmp.contains("kinetic energy") && strTmp.contains("Ekin") && strTmp.contains("=")) {
			    		setDataMd(1,strTmp,iterationMD);
			    	}
			    	if(strTmp.contains("temperature") && strTmp.contains("=")) {
			    		setDataMd(2,strTmp,iterationMD);
			    	}
			    	if(strTmp.contains("Ekin + Etot (const)") && strTmp.contains("=")) {
			    		setDataMd(3,strTmp,iterationMD);
			    	}
		    	}
		    	if(strTmp.contains("ATOMIC_POSITIONS")) {
		    		startCalc = true;
		    		recordAtomicPos = true;//must be after fileData.addAtomicPosition()
		    		this.addNewAtomPosition();
		    		argCache = this.parseArg(strTmp);
		    	}
		    	if(strTmp.contains("CELL_PARAMETERS")) {
		    		startCalc = true;
		    		//ShowAlert.showAlert(AlertType.INFORMATION, "Debug", Integer.toString(lineCount));
		    		this.iGeoTemp.ibrav.setValue(0);//only in case of vc-relax will this be found.
		    		recordCellPara = true;
		    		this.addNewCell();
		    		argCache = this.parseArg(strTmp);
		    	}
		    	if(strTmp.contains("bravais-lattice index") && !startCalc) {
		    		this.parseIBrav(strTmp);
		    	}
		    	if(strTmp.contains("celldm(") && !startCalc) {
		    		this.parseCelldm(strTmp);
		    	}
		    	if(lowerCaseStr.contains("nstep")&& strTmp.contains("=") && !startCalc) {
		    		String[] splitted = strTmp.trim().split("\\s+");//split the string by whitespaces
		    		try {
		    			Integer dbTmp =  Integer.valueOf(splitted[2]);
		    			if(dbTmp!=null) {this.nstep = dbTmp;}
		    		}catch(Exception e) {
		    			e.printStackTrace();
		    		}
		    	}
		    	if(lowerCaseStr.contains("total energy") && strTmp.contains("=")) {
		    		startCalc = true;
		    		String[] splitted = strTmp.trim().split("\\s+");//split the string by whitespaces
		    		try {
		    			if(strTmp.contains("!")) {
			    			Double dbTmp =  Double.valueOf(splitted[4]);
			    			if(dbTmp!=null) {this.addTotalEnergy(dbTmp, true);}
		    			}
		    			else {
		    				Double dbTmp =  Double.valueOf(splitted[3]);
			    			if(dbTmp!=null) {this.addTotalEnergy(dbTmp, false);}
		    			}
		    		}catch(Exception e) {
		    			e.printStackTrace();
		    		}
		    	}
		    	if(lowerCaseStr.contains("total force") && strTmp.contains("=")) {
		    		String[] splitted = strTmp.trim().split("\\s+");//split the string by whitespaces
		    		try {
		    			Double dbTmp =  Double.valueOf(splitted[3]);
		    			if(dbTmp!=null) {this.totalForce.add(dbTmp);}
		    		}catch(Exception e) {
		    			e.printStackTrace();
		    		}
		    	}
		    	if(lowerCaseStr.contains("total   stress") && strTmp.contains("=")) {
		    		String[] splitted = strTmp.trim().split("=");//split the string by =
		    		try {
		    			Double dbTmp =  Double.valueOf(splitted[1].trim());
		    			if(dbTmp!=null) {this.totalPressure.add(dbTmp);}
		    		}catch(Exception e) {
		    			e.printStackTrace();
		    		}
		    	}
		    	if(lowerCaseStr.contains("total magnetization") && strTmp.contains("=")) {
		    		String[] splitted = strTmp.trim().split("\\s+");//split the string by whitespaces
		    		try {
		    			Double dbTmp =  Double.valueOf(splitted[3]);
		    			if(dbTmp!=null) {this.addMag(dbTmp, true);}
		    		}catch(Exception e) {
		    			e.printStackTrace();
		    		}
		    	}
		    	if(lowerCaseStr.contains("absolute magnetization") && strTmp.contains("=")) {
		    		String[] splitted = strTmp.trim().split("\\s+");//split the string by whitespaces
		    		try {
		    			Double dbTmp =  Double.valueOf(splitted[3]);
		    			if(dbTmp!=null) {this.addMag(dbTmp, false);}
		    		}catch(Exception e) {
		    			e.printStackTrace();
		    		}
		    	}
		    	//highest occupied level
		    	if(lowerCaseStr.contains("highest occupied level")) {
		    		String[] splitted = strTmp.trim().split("\\s+");//split the string by whitespaces
		    		try {
		    			Double dbTmp =  Double.valueOf(splitted[4]);
		    			if(dbTmp!=null) {this.setHomo(dbTmp);}
		    		}catch(Exception e) {
		    			e.printStackTrace();
		    		}
		    	}
				if(lowerCaseStr.contains("fermi energy")) {
					setFermi(strTmp);
				}
				if(lowerCaseStr.contains("self-consistent calculation")) {
					this.hasScf = true;
					if(strTmp.toLowerCase().contains("end of")) {this.hasScfFinished=true;}
				}
				if(lowerCaseStr.contains("molecular dynamics calculation")) {
					this.isMD = true;
					if(strTmp.toLowerCase().contains("end of")) {this.isMDFinished=true;}
				}
				if(lowerCaseStr.contains("geometry optimization")) {
					this.isOpt = true;
					if(strTmp.toLowerCase().contains("end of")) {this.isOptFinished=true;}
				}
				if(lowerCaseStr.contains("band structure calculation")) {
					this.isNscf = true;
					if(strTmp.toLowerCase().contains("end of")) {this.isNscfFinished=true;}
				}
				if(lowerCaseStr.contains("dos")) {
					this.isDos = true;
					
				}
				if(this.isDos && strTmp.toLowerCase().contains("terminated")) {this.isDosFinished=true;}
				
				if(strTmp.toUpperCase().contains("JOB DONE")) {
					this.isJobDone = true;
				}
				if(strTmp.contains("%%%")) {//there are two lines sandwiching the error message
					flagError = (!flagError);
					if(!flagError) {errorMessage+=(strTmp+"\n");}//record the last "%%%%%%%%%%%%%" line
				}
				if(flagError && errorLineNum<100) {//limit error message to 100 lines to prevent programming pitfalls
					errorLineNum++;
					errorMessage+=(strTmp+"\n");
				}
		    }
		    
		    sc.close();
		    
		    
		    
		    if(lineCount==0) {
		    	return "No lines detected. File empty or binary file.";
		    }
		    else {
		    	updateGeoAgent();
		    }
		} catch (IOException e) {
			e.printStackTrace();
			return "IOException: "+e.getMessage();
		}
		return "";
	}
	private String parseArg(String strLine) {
		if(strLine==null || !strLine.contains("(") || !strLine.contains(")")) {
			ShowAlert.showAlert(AlertType.INFORMATION, "Error", "missing ( or ) in the line!");
			return null;
		}
		String[] splitted = strLine.trim().split("(\\))|(\\()");
		if(splitted.length<2) {
			ShowAlert.showAlert(AlertType.INFORMATION, "Error", "cannot find arguments between ( and ) in the line!");
			return null;
		}
		return splitted[1].trim();
	}
	public void updateGeoAgent(int indUsed) {
		if(indUsed<0 || indUsed>=this.atomicPositions.size()) {return;}
		//cell parameters, if existed
		if(indUsed<this.cellParameter.size()) {
			loadCellParameter(indUsed);
		}
		//atomic positions
		loadAtomicPositions(indUsed);
		
		//update element list
		this.iGeoTemp.updateElemListAll();//***no need to do it everytime
	}
	public int getTotalSteps() {
		int indTmp = -1;
		if(this.cellParameter.size()>1) {//cell parameters also relaxes
			indTmp = Math.min(this.cellParameter.size(), this.atomicPositions.size());
		}
		else {
			indTmp = this.atomicPositions.size();//cellParameter size must be 1
		}
		return indTmp;
	}
	private void updateGeoAgent() {
		int indTmp = getTotalSteps();
		
		loadAtomicPositions(indTmp-1);
		
		if(this.cellParameter.size()==1) {
			loadCellParameter(0);
		}
		else {
			loadCellParameter(indTmp-1);
		}

		//update element list
		this.iGeoTemp.updateElemListAll();
	}
	private void loadCellParameter(int ind) {
		CellParameter lastCell = this.cellParameter.get(ind);
		this.iGeoTemp.vectorA1.setValue(lastCell.getAx());
		this.iGeoTemp.vectorA2.setValue(lastCell.getAy());
		this.iGeoTemp.vectorA3.setValue(lastCell.getAz());
		this.iGeoTemp.vectorB1.setValue(lastCell.getBx());
		this.iGeoTemp.vectorB2.setValue(lastCell.getBy());
		this.iGeoTemp.vectorB3.setValue(lastCell.getBz());
		this.iGeoTemp.vectorC1.setValue(lastCell.getCx());
		this.iGeoTemp.vectorC2.setValue(lastCell.getCy());
		this.iGeoTemp.vectorC3.setValue(lastCell.getCz());
	}
	private void loadAtomicPositions(int ind) {
		ArrayList<Atom> lastAtom = this.atomicPositions.get(ind);
		//this.iGeoTemp.atomList.clear();//cannot clear here because references!
		this.iGeoTemp.atomList = lastAtom;//*****pass reference here. Be careful. Error here!
	}
	private void parseIBrav(String strLine) {
		//ShowAlert.showAlert(AlertType.INFORMATION, "Debug", "parseIBrav!");
		if(strLine==null || !strLine.contains("=")) {
			ShowAlert.showAlert(AlertType.INFORMATION, "Error", "Wrong line!");return;}
		String[] splitted = strLine.trim().split("=");
		try {
			int ibravTmp = Integer.valueOf(splitted[1].trim());
			this.iGeoTemp.ibrav.setValue(ibravTmp);
		}
		catch(Exception e) {
			e.printStackTrace();
			ShowAlert.showAlert(AlertType.INFORMATION, "Warning", "Cannot read ibrav!");
		}
	}
	
	private void parseCelldm(String strTmp) {
		//ShowAlert.showAlert(AlertType.INFORMATION, "Debug", "parseCelldm!"+strTmp);
		//ShowAlert.showAlert(AlertType.INFORMATION, "Debug", strTmp.contains("(1)")?"(1)":"(4)");
		//ShowAlert.showAlert(AlertType.INFORMATION, "Debug", strTmp.contains("(4)")?"(4)":"(1)");
		
		if(strTmp==null || !strTmp.contains("=")) {
			ShowAlert.showAlert(AlertType.INFORMATION, "Error", "Wrong line!");return;}
		
		//if(this.iGeoTemp.ibrav.equals(0)) return;//DO NOT USE THIS LINE HERE!
		
		boolean isSecondLine=false;
		if(strTmp.contains("(1)")) {isSecondLine=false;}//celldm(1-3)
		else if (strTmp.contains("(4)")) {isSecondLine=true;}//celldm(4-6)
		else {ShowAlert.showAlert(AlertType.INFORMATION, "Error", "Cannot detect lines in celldm");return;}
		
		String[] splitted = strTmp.trim().split("celldm\\(.\\)=");
		
//		ShowAlert.showAlert(AlertType.INFORMATION, "Debug", splitted[1]);
//		ShowAlert.showAlert(AlertType.INFORMATION, "Debug", splitted[2]);
//		ShowAlert.showAlert(AlertType.INFORMATION, "Debug", splitted[3]);
		
		try {
			double celldmTmp1 = Double.valueOf(splitted[1].trim());
			double celldmTmp2 = Double.valueOf(splitted[2].trim());
			double celldmTmp3 = Double.valueOf(splitted[3].trim());
			
			if(isSecondLine) {//celldm(4-6)
				this.iGeoTemp.setCellABCFromCelldm(4, celldmTmp1);
				this.iGeoTemp.setCellABCFromCelldm(5, celldmTmp2);
				this.iGeoTemp.setCellABCFromCelldm(6, celldmTmp3);
			}
			else {//celldm(1-3)
				//A or alat
				//ShowAlert.showAlert(AlertType.INFORMATION, "Debug", Double.toString(celldmTmp1));
				this.iGeoTemp.setCellABCFromCelldm(1, celldmTmp1);
				this.iGeoTemp.setCellABCFromCelldm(2, celldmTmp2);
				this.iGeoTemp.setCellABCFromCelldm(3, celldmTmp3);
				this.alat = celldmTmp1;
			}
		}
		catch(Exception e) {
			e.printStackTrace();
			ShowAlert.showAlert(AlertType.INFORMATION, "Warning", "Cannot read celldm!");
		}
	}
	private Point3D getCoor(String strLine) {
		//strTmp should have the format of "... = (   0.2500000   0.2500000   0.2500000  )"
		String[] splitted = strLine.trim().split("(\\))|(\\()");
		String strTmpNumber = splitted[splitted.length-1];
		String[] splittedNumber = strTmpNumber.trim().split("\\s+");
		if(splittedNumber.length!=3) {
			ShowAlert.showAlert(AlertType.INFORMATION, "Error", "Wrong atom positions!");return null;}
		Double x,
		y,
		z;
		try{
			x = Double.valueOf(splittedNumber[0]);
			y = Double.valueOf(splittedNumber[1]);
			z = Double.valueOf(splittedNumber[2]);
		}
		catch(Exception e) {
			ShowAlert.showAlert(AlertType.INFORMATION, "Error", "Atom positions not number!");
			e.printStackTrace();
			return null;
		}
		if(x==null || y==null || z==null) {return null;}
		return new Point3D(x,y,z);
	}
	private void parseInitialCellPara(String strLine) {
		Point3D pTmp;
		if(strLine.contains("(1)") || strLine.contains("(2)") || strLine.contains("(3)")) {
			pTmp = getCoor(strLine);
			//if(pTmp==null) {return;}
			cellParameter.get(0).addCoor(pTmp.getX(),pTmp.getY(),pTmp.getZ());
		}
		else {ShowAlert.showAlert(AlertType.INFORMATION, "Error", "parseInitialCellPara: "+strLine);}

	}
	private void parseInitialAtomPos(String strLine) {
		//here it must be in alat unit
		
		//ShowAlert.showAlert(AlertType.INFORMATION, "Debug", "parseInitialAtomPos!");
		String[] splittedForAtom = strLine.trim().split("\\s+");
		String atomName = splittedForAtom[1].trim();
		//ShowAlert.showAlert(AlertType.INFORMATION, "Debug", atomName);

		ChemicalElements ceTmp;
		
		try{
			ceTmp = ChemicalElements.valueOf(atomName);
		}
		catch(Exception e) {
			ShowAlert.showAlert(AlertType.INFORMATION, "Error", "Wrong atom type!");
			e.printStackTrace();
			return;
		}
		Point3D pTmp = getCoor(strLine);
		if(ceTmp==null || pTmp==null) {return;}
		atomicPositions.get(0).add(new Atom(ceTmp,pTmp.getX(),pTmp.getY(),pTmp.getZ()));
		
	}
//	private void parseAlat(String strLine) {
//		if(strLine==null || !strLine.contains("=")) {
//			ShowAlert.showAlert(AlertType.INFORMATION, "Error", "Wrong line!");return;}
//		String[] splitted = strLine.trim().split("=");
////		//remove everything except numbers (0-9) or dot (.) or minus sign (-)
////		try {
////			double alatTmp = Double.valueOf(splitted[1].replaceAll("[^\\d.-]", ""));
////			if(this.alat!=null && this.alat!=alatTmp) {
////				ShowAlert.showAlert(AlertType.INFORMATION, "Warning", "alat not consistent at different steps!");
////			}
////			this.alat = alatTmp;
////		}
////		catch(Exception e) {
////			e.printStackTrace();
////		}
//		try {
//			String[] splitted2 = splitted[1].trim().split("a");
//			double alatTmp = Double.valueOf(splitted2[0]);
//			if(this.alat!=null && this.alat!=alatTmp) {
//				ShowAlert.showAlert(AlertType.INFORMATION, "Warning", "alat not consistent at different steps!");
//			}
////			this.alat = alatTmp;
////			this.iGeoTemp.unitCellLength = EnumUnitCellLength.bohr;
////			this.iGeoTemp.cellA.setValue(alatTmp);
//		}
//		catch(Exception e) {
//			e.printStackTrace();
//			ShowAlert.showAlert(AlertType.INFORMATION, "Warning", "Cannot read alat!");
//		}
//	}
	public void addNewAtomPosition() {
		atomicPositions.add(new ArrayList<Atom>());
	}
	public void addNewCell() {
		cellParameter.add(new CellParameter());
	}
	public boolean addCellParameter(String strLine, String argCache) {
		//now cellParameter.size() must >= 2
		String[] splitted = strLine.trim().split("\\s+");//split the string by whitespaces
		if(splitted.length<3) {return false;}//end of one cell_para
		
		Double x=null,
		y=null,
		z=null;
		try {
			x = Double.valueOf(splitted[0]);
			y = Double.valueOf(splitted[1]);
			z = Double.valueOf(splitted[2]);
		}catch(Exception e) {
			return false;
		}
		if(x==null || y==null || z==null) {return false;}
		
		//actually here it cannot be in crystal unit. But not necessary to check
		Point3D ptNew = convert2alat(argCache, x, y, z);
		if(ptNew==null) {return false;}
		
		cellParameter.get(cellParameter.size()-1).addCoor(ptNew.getX(),ptNew.getY(),ptNew.getZ());
		
		return true;
	}
	public boolean addAtomicPosition(String strLine, String argCache) {
		//return false if no atom position is added
		
		if(strLine==null || strLine.isEmpty() || strLine.trim().length()==0) {return false;}
		if(strLine.contains("End final coordinates")) {finalPosition=true; return false;}
		String[] splitted = strLine.trim().split("\\s+");//split the string by whitespaces
		if(splitted.length<4) {return false;}
		ChemicalElements atomSpecies=null;
		Double x=null,
		y=null,
		z=null;
		try {
			atomSpecies = ChemicalElements.valueOf(splitted[0]);
			x = Double.valueOf(splitted[1]);
			y = Double.valueOf(splitted[2]);
			z = Double.valueOf(splitted[3]);
		}catch(Exception e) {
			return false;
		}
		if(atomSpecies==null || x==null || y==null || z==null) {return false;}
		
		Point3D ptNew = convert2alat(argCache, x, y, z);
		if(ptNew==null) {return false;}
		
		atomicPositions.get(atomicPositions.size()-1).add(new Atom(atomSpecies,ptNew.getX(),ptNew.getY(),ptNew.getZ()));
		return true;
	}
	public Point3D convert2alat(String argCache, double x, double y, double z) {
		Point3D ptOld = new Point3D(x,y,z);

		if(argCache==null || argCache.isEmpty() || argCache.contains("alat")) {
			return ptOld;//use alat as a default. True for both atomic positions and cell parameters
		}
		else if("crystal".equals(argCache)) {
			//cellParameter.get(0) must be in alat unit (header of stdout file)
			return cellParameter.get(0).crystalToCoordinate(x, y, z);
		}
		else if("bohr".equals(argCache)) {
			//this.alat must have the unit of bohr
			if(this.alat == null || this.alat<=0) {
				ShowAlert.showAlert(AlertType.INFORMATION, "Error", "alat must be positive.");return null;}
			return ptOld.multiply(1.0/this.alat);
		}
		else if("angstrom".equals(argCache)) {
			//this.alat must have the unit of bohr. Need unit conversion here
			if(this.alat == null || this.alat<=0) {
				ShowAlert.showAlert(AlertType.INFORMATION, "Error", "alat must be positive.");return null;}
			return ptOld.multiply(1.0/PhysicalConstants.angstPerBohr/this.alat);
		}
		else {
			ShowAlert.showAlert(AlertType.INFORMATION, "Error", "Unrecognized argument: "+argCache);
			return null;
		}
	}
	public ArrayList<ArrayList<Double>> getDosArray() {
		return dosArray;
	}
	public ArrayList<String> getDosHeader() {
		return dosHeader;
	}
	public ArrayList<ArrayList<Double>> getTddftArray() {
		return tddftArray;
	}
	public ArrayList<String> getTddftHeader() {
		return tddftHeader;
	}
	
	public void addTotalEnergy(double ene, boolean isFinal) {
		//here, ene and isFinal are primitive types that CANNOT be null
		//energyArray==null shouldn't happen
		if(energyArray.isEmpty()) {energyArray.add(new ArrayList<Double>());}
		energyArray.get(energyArray.size()-1).add(ene);
		if(isFinal) {energyArray.add(new ArrayList<Double>());
		flagScfFinishedForTotalMag=true;
		flagScfFinishedForAbsMag=true;}
	}
	public void addMag(double mag, boolean isTotal) {
		ArrayList<ArrayList<Double>> tmpMag = isTotal?totalMag:absoluteMag;
		//tmpMag==null shouldn't happen
		if(tmpMag.isEmpty()) {tmpMag.add(new ArrayList<Double>());}
		tmpMag.get(tmpMag.size()-1).add(mag);
		if(flagScfFinishedForTotalMag&&isTotal) {flagScfFinishedForTotalMag=false;tmpMag.add(new ArrayList<Double>());}
		if(flagScfFinishedForAbsMag&&!isTotal) {flagScfFinishedForAbsMag=false;tmpMag.add(new ArrayList<Double>());}
	}
	public ArrayList<ArrayList<Double>> getEnergyArray(){
		return this.energyArray;
	}
	public void setFermi(double fl) {
		fermiLevel.add(fl);
	}
	public void setHomo(double hm) {
		homoLevel.add(hm);
	}
	public void addDosHeader(String line) {
		line = line.replace("#", "");
		try {
			String[] parts1 = line.split("[\\)]");
			String[] parts2 = line.split("=");
			String[] parts3 = parts2[1].split("e");
			fermiDos=Double.valueOf(parts3[0]);
			dosHeader.clear();
			for(int i=0;i<parts1.length-1;i++) {
				dosHeader.add(parts1[i]+")");
			}
		}
		catch(Exception e) {
			e.printStackTrace();
		}
	}
	public void addTddftHeader(String line) {
		line = line.replace("#", "").trim();
		try {
			String[] parts1 = line.split("[\\)]");
			tddftHeader.clear();
			for(int i=0;i<parts1.length;i++) {
				tddftHeader.add(parts1[i].trim()+(i==parts1.length-1?"":")"));
			}
		}
		catch(Exception e) {
			e.printStackTrace();
		}
	}
	public String toString() {
		String strTmp = "";

		if(EnumFileCategory.dos.equals(fileCategory)) {
			//DOS data file
			strTmp+="DOS data file.\n";

			if(dosHeader.size()>0) {
				strTmp+=("Fermi level DOS: "+(fermiDos==null?"null":Double.toString(fermiDos))+"\n");
				strTmp+=dosHeader.get(0);
			}
			if(dosArray.size()>0 && dosArray.get(0).size()>0 && dosArray.get(dosArray.size()-1).size()>0) {
				strTmp+=("(E DOS) from "+Double.toString(dosArray.get(0).get(0))+" to "+
						Double.toString(dosArray.get(dosArray.size()-1).get(0))+"\n");
			}
			
		}
		else if(EnumFileCategory.tddftPlotSDat.equals(fileCategory)) {
			//DOS data file
			strTmp+="TDDFT Plot_S data file.\n";

			if(tddftHeader.size()>0) {
				strTmp+="Headers: ";
				for(int i=0;i<tddftHeader.size();i++) {
					strTmp+=(tddftHeader.get(i)+",");
				}
				strTmp+="\n";
				strTmp+=tddftHeader.get(0);
			}
			if(tddftArray.size()>0 && tddftArray.get(0).size()>0 && tddftArray.get(tddftArray.size()-1).size()>0) {
				strTmp+=("(Energy) from "+Double.toString(tddftArray.get(0).get(0))+" to "+
						Double.toString(tddftArray.get(tddftArray.size()-1).get(0))+"\n");
			}
			
		}
		else if(EnumFileCategory.bandsDatGnu.equals(fileCategory)) {
			if(fermiDos!=null) {
				strTmp+="Fermi energy read: "+fermiDos.toString()+".\n\n";
			}
			if(bandsDatArray.isEmpty() || (bandsDatArray.size()==1 && bandsDatArray.get(0).isEmpty())) {
				strTmp+="Empty bands data file.\n\n";
			}
			else {
				strTmp+=Integer.toString(
						bandsDatArray.get(bandsDatArray.size()-1).isEmpty() ? bandsDatArray.size()-1:bandsDatArray.size());
				strTmp+=" bands read in total.\n\n";
			}
			if(bandsHighSymmetryK.isEmpty() || bandsHighSymmetryKXCoor.isEmpty()) {
				strTmp+="Empty high symmetry K.\n\n";
			}
			else if(bandsHighSymmetryK.size()!=bandsHighSymmetryKXCoor.size()) {
				strTmp+="Inconsistent high symmetry K points.\n\n";
			}
			else {
				for(int i=0;i<bandsHighSymmetryK.size();i++) {
					strTmp+=("high-symmetry point:"+bandsHighSymmetryK.get(i)+
							", x coordinate:"+bandsHighSymmetryKXCoor.get(i).toString()+"\n");
				}
				strTmp+="\n";
			}
		}
		else if(EnumFileCategory.stdout.equals(fileCategory)) {
			//stdout file
			strTmp+="Standard output file.\n";
			//calculation type
			strTmp+="Detected calculation type:";
			if(nstep==1 && hasScf) {strTmp+="SCF,";}
			if(isMD) {strTmp+="MD,";}
			if(isOpt) {strTmp+="Optimization,";}
			if(isNscf) {strTmp+="NSCF,";}
			if(isDos) {strTmp+="DOS,";}
			if(this.isPwBands) {strTmp+="pwscf bands calculation.\n";}
			if(this.isBandsPP) {strTmp+="bands program.\n";}
			if(isTddftTurbo) {strTmp+="turbo TDDFT program.\n";}
			if(isTddftSpectrum) {strTmp+="TDDFT spectrum (post-processing) program.\n";}
			if(strTmp.endsWith("type:")) {strTmp+="Unknown.\n";}
			
			//finished or not
			if(nstep==1 && hasScf) {strTmp+=(hasScfFinished?"SCF finished.":"SCF not finished.")+"\n";}
			if(isMD) {strTmp+=(isMDFinished?"MD finished.":"MD not finished.")+"\n";}
			if(isOpt) {strTmp+=(isOptFinished?"Optimization finished.":"Optimization not finished.")+"\n";}
			if(isNscf) {strTmp+=(isNscfFinished?"NSCF finished.":"NSCF not finished.")+"\n";}
			if(isDos) {strTmp+=(isDosFinished?"DOS finished.":"DOS not finished.")+"\n";}
			
			//the whole job finished or not (last line of the output file)
			if(isJobStart) {strTmp+=(isJobDone?"Job done.\n":"Job not done yet.\n");}
			
			//error message or not
			if(!errorMessage.isEmpty()) {
				strTmp+=("Error message detected:\n"+errorMessage+"\n");
			}
			
			//total energy
			int cnt = 0;
			if(isMD || isOpt || hasScf) {
				
				if(energyArray.size()<=2) {
					strTmp+="Total energy (Ry):";
					for(ArrayList<Double> ard:energyArray) {
						if(ard!=null) {
							cnt++;
							if(ard.isEmpty()) {continue;}
							strTmp+=("Step "+Integer.toString(cnt)+": ");
							for(Double val:ard) {
								if(val!=null) {strTmp+=(val.toString()+",");}
							}
							strTmp+="\n";
						}
					}
				}
				else {
					strTmp+="Total energy converged (Ry):";
					for(ArrayList<Double> ard:energyArray) {
						if(ard!=null) {
							cnt++;
							if(ard.isEmpty()) {continue;}
							strTmp+=("Step "+Integer.toString(cnt)+": "+ard.get(ard.size()-1).toString()+",");
						}
						if((cnt % 5) == 0) {
							strTmp+="\n";
						}
					}
					strTmp+="\n";
					
				}
				if(totalForce!=null && !totalForce.isEmpty()) {
					strTmp+="Total force (Ry/Bohr):";
					for(Double val:this.totalForce) {
						if(val!=null) {strTmp+=(val.toString()+",");}
					}
					strTmp+="\n";
				}
				if(this.totalPressure!=null && !totalPressure.isEmpty()) {
					strTmp+="Pressure (kbar):";
					for(Double val:this.totalPressure) {
						if(val!=null) {strTmp+=(val.toString()+",");}
					}
					strTmp+="\n";
				}
			}
			
			//magnetization
			int cnt_mag = 0;
			if(isMD || isOpt || hasScf) {
				if(!totalMag.isEmpty() || !absoluteMag.isEmpty()) {
					strTmp+="Total magnetization (Bohr mag/cell):";
					for(ArrayList<Double> ard:totalMag) {
						if(ard!=null) {
							cnt_mag++;
							if(ard.isEmpty()) {continue;}
							strTmp+=("Step "+Integer.toString(cnt_mag)+": ");
							for(Double val:ard) {
								if(val!=null) {strTmp+=(val.toString()+",");}
							}
							strTmp+="\n";
						}
					}
					cnt_mag = 0;
					strTmp+="Absolute magnetization (Bohr mag/cell):";
					for(ArrayList<Double> ard:absoluteMag) {
						if(ard!=null) {
							cnt_mag++;
							if(ard.isEmpty()) {continue;}
							strTmp+=("Step "+Integer.toString(cnt_mag)+": ");
							for(Double val:ard) {
								if(val!=null) {strTmp+=(val.toString()+",");}
							}
							strTmp+="\n";
						}
					}
				}
			}
			
			//Fermi
			if(isMD || isOpt || hasScf || isNscf || isDos) {
				strTmp+="Fermi energy: ";
				if(fermiLevel.isEmpty()) {strTmp+="Unknown\n";}
				else {
					for(Double val:fermiLevel) {
						if(val!=null) {strTmp+=(val.toString()+",");}
					}
					strTmp+=" eV\n";
				}
				//HOMO
				strTmp+="Highest occupied level: ";
				if(homoLevel.isEmpty()) {strTmp+="Unknown\n";}
				else {
					for(Double val:homoLevel) {
						if(val!=null) {strTmp+=(val.toString()+",");}
					}
					strTmp+=" eV\n";
				}
			}
			
			//Geometry
			if(isMD || isOpt) {
				if(atomicPositions!=null && atomicPositions.size()>0) {
					strTmp+="ATOMIC_POSITIONS: "+Integer.toString(atomicPositions.size())+"\n";
					strTmp+="Last position"+(finalPosition?"(final)":"(not final)")+"\n";
					for(Atom atomTmp : atomicPositions.get(atomicPositions.size()-1)) {
						strTmp+=(atomTmp.printPositions()+"\n");
					}
				}
				if(cellParameter!=null && cellParameter.size()>0) {
					strTmp+="CELL_PARAMETERS: "+Integer.toString(cellParameter.size())+"\n";
					strTmp+=("Last cell:\n"+cellParameter.get(cellParameter.size()-1).toString()+"\n");
				}
				if(alat!=null) {
					strTmp+="alat: "+Double.toString(alat)+"\n";
				}
			}
			
			if(isMD) {
				//indexMd:
				//0, time in ps
				//1, Ekin in Ry
				//2, temperature in K
				//3, total energy (should be constant) in Ry
				strTmp+="Time in ps: ";
				for(int i=0;i<this.dataMd.get(0).size();i++) {
					strTmp+=Double.toString(this.dataMd.get(0).get(i))+",";
				}
				strTmp+="\nKinetic Energy in Ry: ";
				for(int i=0;i<this.dataMd.get(1).size();i++) {
					strTmp+=Double.toString(this.dataMd.get(1).get(i))+",";
				}
				strTmp+="\nTemperature in K: ";
				for(int i=0;i<this.dataMd.get(2).size();i++) {
					strTmp+=Double.toString(this.dataMd.get(2).get(i))+",";
				}
				strTmp+="\nTotal energy (constant) in Ry: ";
				for(int i=0;i<this.dataMd.get(3).size();i++) {
					strTmp+=Double.toString(this.dataMd.get(3).get(i))+",";
				}
				strTmp+="\n";
			}
			
		
		}
		strTmp+="\n";
		return strTmp;
	}
	public ArrayList<String> getBandsHighSymmetryK() {
		return bandsHighSymmetryK;
	}
	public ArrayList<Double> getBandsHighSymmetryKXCoor() {
		return bandsHighSymmetryKXCoor;
	}
	public ArrayList<Double> getTotalForce() {
		return totalForce;
	}
	public ArrayList<Double> getTotalPressure() {
		return totalPressure;
	}
	public ArrayList<ArrayList<Double>> getDataMd(){
		return this.dataMd;
	}
}
