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
import java.io.FileReader;
import java.io.IOException;
import java.io.LineNumberReader;
import java.util.ArrayList;
import java.util.Scanner;

import com.consts.Constants.EnumFileCategory;
import com.consts.Constants.EnumStep;
import com.consts.Constants.EnumUnitCellAngle;
import com.consts.Constants.EnumUnitCellLength;
import com.consts.Constants.EnumUnitCellParameter;
import com.programconst.ProgrammingConstsQE;
import agent.InputAgentGeo;
import agent.InputAgentPhonon;
import app.input.CellParameter;
import app.input.Kpoint;
import app.input.geo.Atom;
import core.com.consts.ChemicalElements;
import core.com.consts.PhysicalConstants;
import core.com.error.ShowAlert;
import core.com.programconst.ProgrammingConsts;
import javafx.geometry.Point3D;
import javafx.scene.control.Alert.AlertType;

public class FileDataClass {
	private ArrayList<ArrayList<Double>> energyArray;//Ry
	private ArrayList<Double> fermiLevel;//eV
	private ArrayList<Double> homoLevel;//eV
	private ArrayList<Double> totalForce;//Ry/Bohr
	private ArrayList<Double> totalPressure;//kBar
	
	private ArrayList<ArrayList<Double>> totalMag,
	totalMagy,
	totalMagz;//Bohr mag/cell
	
	
	private ArrayList<ArrayList<Double>> absoluteMag;//Bohr mag/cell
	private ArrayList<ArrayList<Double>> dosArray;
	private ArrayList<String> dosHeader;
	private ArrayList<ArrayList<ArrayList<Double>>> bandsDatArray;
	private ArrayList<Double> bandsHighSymmetryKXCoor;
	private ArrayList<String> bandsHighSymmetryK;
	
	//phonon
	private ArrayList<String> phOutInfo;
	private ArrayList<ArrayList<Double>> phononBandsDatArray;
	private ArrayList<Kpoint> phononKPoints;
	private String phononDielectricInfo = "";
	
	private ArrayList<ArrayList<Double>> tddftArray;
	private ArrayList<String> tddftHeader;
	
	private ArrayList<ArrayList<Double>> dataMd;//4*n dimension
	
	//NEB
	private ArrayList<ArrayList<Double>> nebEnergy;
	private ArrayList<ArrayList<Double>> nebError;
	private ArrayList<Double> nebBarrierFwd;
	private ArrayList<Double> nebBarrierBwd;
	
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
	public boolean isPW = false;
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
	public boolean isPH = false;
	public boolean isNeb = false;
	public boolean isHybrid = false;
	
	
	//will be true when one scf just finished. Will be set back to false when one new mag is read
	private boolean flagScfFinishedForTotalMag=false;
	private boolean flagScfFinishedForTotalMagy=false;
	private boolean flagScfFinishedForTotalMagz=false;
	private boolean flagScfFinishedForAbsMag=false;
	
	public FileDataClass() {
		energyArray = new ArrayList<ArrayList<Double>>();
		fermiLevel = new ArrayList<Double>();
		homoLevel = new ArrayList<Double>();
		totalForce = new ArrayList<Double>();
		totalPressure = new ArrayList<Double>();
		
		totalMag = new ArrayList<ArrayList<Double>>();
		totalMagy = new ArrayList<ArrayList<Double>>();
		totalMagz = new ArrayList<ArrayList<Double>>();
		
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
				
		phOutInfo = new ArrayList<String>();
		phononBandsDatArray = new ArrayList<ArrayList<Double>>();
		phononKPoints = new ArrayList<Kpoint>();
		
		dataMd = new ArrayList<ArrayList<Double>>();//DO NOT CLEAR dataMd itself!
		dataMd.add(new ArrayList<Double>());//time in ps
		dataMd.add(new ArrayList<Double>());//Ekin
		dataMd.add(new ArrayList<Double>());//temperature
		dataMd.add(new ArrayList<Double>());//total energy (should be constant)
		
		nebEnergy = new ArrayList<ArrayList<Double>>();
		nebError = new ArrayList<ArrayList<Double>>();
		nebBarrierFwd = new ArrayList<Double>();
		nebBarrierBwd = new ArrayList<Double>();
	}
	public ArrayList<ArrayList<ArrayList<Double>>> getBandsDatArray(){
		return this.bandsDatArray;
	}
	public <T> void clearArray(ArrayList<T> arr) {
		if(arr!=null) {
			for(T ard:arr) {
				if(ard!=null && ard.getClass()==ArrayList.class) {
					//ShowAlert.showAlert("Debug", ard.toString());
					((ArrayList<?>)ard).clear();
				}
			}
			arr.clear();
		}
	}
	public void clearAll() {
		clearArray(energyArray);
		clearArray(totalMag);
		clearArray(totalMagy);
		clearArray(totalMagz);
		clearArray(absoluteMag);
		clearArray(dosArray);
		clearArray(phononBandsDatArray);
		clearArray(tddftArray);
		clearArray(nebEnergy);
		clearArray(nebError);
		clearArray(atomicPositions);

		for(ArrayList<ArrayList<Double>> ard:bandsDatArray) {
			if(ard!=null) {
				for(ArrayList<Double> ard1:ard) {
					if(ard1!=null) {ard1.clear();}
				}
				ard.clear();
			}
		}
		bandsDatArray.clear();
		
		for(ArrayList<Double> arr:dataMd) {
			arr.clear();//DO NOT CLEAR dataMd itself!
		}

		fermiLevel.clear();
		homoLevel.clear();
		totalForce.clear();
		totalPressure.clear();

		dosHeader.clear();
		
		bandsHighSymmetryK.clear();
		bandsHighSymmetryKXCoor.clear();

		tddftHeader.clear();
		
		phOutInfo.clear();
		phononKPoints.clear();
		phononDielectricInfo = "";
		
		nebBarrierFwd.clear();
		nebBarrierBwd.clear();
		
		errorMessage = "";
		
		//not necessary, because atom positions not encoded there. 
		//Further, DO NOT DO IT otherwise the workscene3d will not work for the in/out
		//iGeoTemp = new InputAgentGeo();
		
		alat = null;
		cellParameter.clear();
		finalPosition=false;
		
		nstep=1;fermiDos=null;
		isJobDone=false;
		isJobStart = false;
		hasScf=false;hasScfFinished=false;isMD=false;isMDFinished=false;isOpt=false;isOptFinished=false;
		isNscf=false;isNscfFinished=false;isDos=false;isDosFinished=false;isPW=false;isPH=false;
		isPwBands = false;isBandsPP = false;isTddftTurbo = false;isTddftSpectrum=false;isNeb = false;isHybrid = false;
		flagScfFinishedForTotalMag=false;
		flagScfFinishedForTotalMagy=false;
		flagScfFinishedForTotalMagz=false;
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
	public boolean loadPhononBands(File gnuDatFile) {
		if(!gnuDatFile.canRead()) {
			return false;
		}
		this.clearAll();
		
		try {
			//load .gnu file
		    Scanner sc2 = new Scanner(gnuDatFile); 
		    String strTmp;
		    
		    while (sc2.hasNextLine()) {

		    	strTmp = sc2.nextLine();
		    	
		    	if(strTmp==null || strTmp.trim().isEmpty()) {
		    		continue;
		    	}
		    	addDoubleRow(strTmp,phononBandsDatArray);
	    	}
		    sc2.close();
		} catch (IOException e) {
			e.printStackTrace();
			return false;
		} 
		
		File matDynInputFile = new File(gnuDatFile.getParentFile(),EnumStep.MATDYN.toString()+ProgrammingConsts.stdinExtension);

		if(matDynInputFile.canRead()) {
			//ShowAlert.showAlert(AlertType.INFORMATION, "debug", matDynInputFile.toString());
			InputAgentPhonon iPh = new InputAgentPhonon();
			//ShowAlert.showAlert(AlertType.INFORMATION, "debug", readStringFromFile(matDynInputFile));
			iPh.convertInfoFromInput(readStringFromFile(matDynInputFile));
			if(!iPh.listKPoints.isEmpty()) {phononKPoints = iPh.listKPoints;}
		}
		return true;
	}
	private String readStringFromFile(File fl) {
		if(fl==null || !fl.canRead()) {return "";}

		if(fl.canRead()) {
			try {
				LineNumberReader count1 = new LineNumberReader(new FileReader(fl));
				while (count1.skip(Long.MAX_VALUE) > 0)
			    {
					// Loop just in case the file is > Long.MAX_VALUE or skip() decides to not read the entire file
			    }
				int totalLineNum = count1.getLineNumber() + 1;
				count1.close();
				
			    Scanner sc = new Scanner(fl); 
			  
			    String strTmp="";
			    int lineCount=0;
			    boolean flagSkip = false;
			    
			    while (sc.hasNextLine()) {
			    	lineCount++;
			    	if(lineCount > ProgrammingConsts.maxLinesShownInText && lineCount < totalLineNum-ProgrammingConsts.maxLinesShownInText){
			    		if(!flagSkip) {
			    			strTmp+=("------------------------------+------------------------+------------------------------\n"+
			    							 "------------------------------+------------------------+------------------------------\n"+
			    							 "------------------------------+-------skip "+
			    							 Integer.toString(totalLineNum-2*ProgrammingConsts.maxLinesShownInText)+" lines-------+------------------------------\n"+
			    							 "------------------------------+------------------------+------------------------------\n"+
			    							 "------------------------------+------------------------+------------------------------\n");
			    		}
			    		flagSkip = true;
			    		continue;
		    		}
			    	else {
			    		strTmp+= (sc.nextLine()+"\n");
			    	}
	
		    	}
			    sc.close();
			    return strTmp;
			} catch (IOException e) {
				e.printStackTrace();
			} 
		}
		return "";
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
		    String phononCache = "";
		    boolean flagPhononStop = true;//true is not recording
		    boolean flagDielectricStop = true;//true is not recording
		    boolean flagNebRecord = false;//false is not recording
		    
		    while (sc.hasNextLine()) {
		    	lineCount++;
		    	strTmp = sc.nextLine();
		    	//total energy
		    	if(strTmp==null || strTmp.isEmpty()) continue;
		    	
		    	String lowerCaseStr = strTmp.toLowerCase();
		    	
		    	if(this.isPW) {
			    	if(recordAtomicPos) {
			    		recordAtomicPos = this.addAtomicPosition(strTmp,argCache);
			    	}
			    	if(recordCellPara) {
			    		recordCellPara = this.addCellParameter(strTmp,argCache);
			    	}
		    	}
		    	
		    	if(strTmp.contains("Program PWSCF")) {
		    		this.isPW = true;
		    	}
		    	if(strTmp.contains("plot nbnd")) {
		    		this.isPwBands = true;
		    	}
		    	if(strTmp.contains("Program BANDS")) {
		    		this.isBandsPP = true;
		    	}
		    	if(strTmp.contains("Program NEB")) {
		    		this.isNeb = true;
		    	}
		    	if(strTmp.contains("Program turboTDDFT")) {
		    		this.isTddftTurbo = true;
		    	}
		    	if(strTmp.contains("Program TDDFPT_PP")) {
		    		this.isTddftSpectrum = true;
		    	}
		    	if(strTmp.contains("Program PHONON")) {
		    		this.isPH = true;
		    	}
		    	if(strTmp.contains("starts")) {
		    		this.isJobStart = true;
		    	}
		    	if(strTmp.contains("EXX: now go back to refine")) {
		    		this.isHybrid = true;
		    	}
		    	if(this.isNeb) {
		    		if(strTmp.contains("--- iteration")){
		    			this.nebEnergy.add(new ArrayList<Double>());
		    			this.nebError.add(new ArrayList<Double>());
		    		}
		    		if(strTmp.contains("activation energy (->) =")){
		    			Double dbTmp =  parseDouble(strTmp,4);
		    			if(dbTmp!=null) {this.nebBarrierFwd.add(dbTmp);}
		    			else{
		    				ShowAlert.showAlert("Warning", "Cannot extract activation energy from line "+strTmp);
		    			}
		    		}
		    		if(strTmp.contains("activation energy (<-) =")){
		    			Double dbTmp =  parseDouble(strTmp,4);
		    			if(dbTmp!=null) {this.nebBarrierBwd.add(dbTmp);}
		    			else{
		    				ShowAlert.showAlert("Warning", "Cannot extract activation energy from line "+strTmp);
		    			}
		    		}
		    		if(flagNebRecord) {
		    			flagNebRecord = parseNebEnergy(strTmp);
		    		}
		    		if(strTmp.contains("image        energy (eV)")){
		    			flagNebRecord = true;
		    		}
		    	}
		    	if(this.isPW) {
			    	if(strTmp.contains("tau(") && !startCalc) {
			    		this.parseInitialAtomPos(strTmp);
			    	}
			    	if(strTmp.trim().startsWith("a(") && strTmp.contains(") = (") && !startCalc) {
			    		this.parseInitialCellPara(strTmp);
			    	}
		    	}
		    	if(this.isPH) {
		    		
		    		//stdout file for ph.x
		    		if(strTmp.contains("Diagonalizing the dynamical matrix")) {
		    			flagPhononStop = false;
		    			phononCache = "";
		    		}
		    		else if(strTmp.contains("*******") || strTmp.trim().isEmpty() || strTmp.contains("Mode symmetry") 
		    				|| (strTmp.contains(")") && strTmp.contains("="))) {
		    			if(!flagPhononStop) {
		    				phononCache+=(strTmp+"\n");
		    			}
		    		}
		    		else{
		    			if(!phononCache.isEmpty()) {
			    			flagPhononStop = true;
			    			this.phOutInfo.add(phononCache);
			    			phononCache = "";
		    			}
		    		}
		    		
		    		//dielectric constant and effective charges (the information will appear twice in the file. This will read twice and take the last one)
		    		if(strTmp.contains("Dielectric constant in cartesian axis")) {
		    			flagDielectricStop = false;
		    			phononDielectricInfo = "";
		    		}
		    		else if(!strTmp.trim().isEmpty() && !strTmp.contains("(") 
		    				&& !strTmp.contains("Effective charges") && !strTmp.contains("atom")){
		    			flagDielectricStop = true;
		    		}
		    		if(!flagDielectricStop) {
		    			phononDielectricInfo+=(strTmp+"\n");
		    		}
		    		
		    		
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
		    	if(this.isPW) {
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
			    		parseTotalMagnetization(strTmp);
			    	}
			    	if(lowerCaseStr.contains("absolute magnetization") && strTmp.contains("=")) {
			    		String[] splitted = strTmp.trim().split("\\s+");//split the string by whitespaces
			    		try {
			    			Double dbTmp =  Double.valueOf(splitted[3]);
			    			if(dbTmp!=null) {this.addMag(dbTmp, 0);}
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
		    	}
				if(lowerCaseStr.contains("dos") && !lowerCaseStr.contains("local")) {
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
	private Double parseDouble(String strLine, int index) {
		String[] splitted = strLine.trim().split("\\s+");//split the string by whitespaces
		try {
			Double dbTmpx =  Double.valueOf(splitted[index]);
			return dbTmpx;
		}catch(Exception e) {
			e.printStackTrace();
		}
		return null;
	}
	private boolean parseNebEnergy(String strLine) {
		//return true to continue
		//return false to abort recording
		if(strLine.trim().isEmpty()) {return true;}
		
		String[] splitted = strLine.trim().split("\\s+");//split the string by whitespaces
		try {
			Double dbTmpEnergy =  Double.valueOf(splitted[1]);
			Double dbTmpError =  Double.valueOf(splitted[2]);
			if(dbTmpEnergy!=null && dbTmpError!=null) {//&& !nebEnergy.isEmpty() && !nebError.isEmpty()
				nebEnergy.get(nebEnergy.size()-1).add(dbTmpEnergy);
				nebError.get(nebError.size()-1).add(dbTmpError);
				return true;
			}
		}catch(Exception e) {
			//e.printStackTrace();
		}
		return false;
	}
	private void parseTotalMagnetization(String strLine) {
		String[] splitted = strLine.trim().split("\\s+");//split the string by whitespaces
		try {
			Double dbTmpx =  Double.valueOf(splitted[3]);
			if(dbTmpx!=null) {this.addMag(dbTmpx, 1);}
			try {
				Double dbTmpy =  Double.valueOf(splitted[4]);
				Double dbTmpz =  Double.valueOf(splitted[5]);
				if(dbTmpy!=null && dbTmpz!=null) {
					this.addMag(dbTmpy, 2);
					this.addMag(dbTmpz, 3);
				}
			}
			catch(Exception e) {
				//nothing to do
			}
		}catch(Exception e) {
			e.printStackTrace();
		}
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
		if(isFinal) {
			energyArray.add(new ArrayList<Double>());
			flagScfFinishedForTotalMag=true;
			flagScfFinishedForAbsMag=true;
			flagScfFinishedForTotalMagy=true;
			flagScfFinishedForTotalMagz=true;
		}
	}
//	public void addMag(double mag, boolean isTotal) {
//		ArrayList<ArrayList<Double>> tmpMag = isTotal?totalMag:absoluteMag;
//		//tmpMag==null shouldn't happen
//		if(tmpMag.isEmpty()) {tmpMag.add(new ArrayList<Double>());}
//		tmpMag.get(tmpMag.size()-1).add(mag);
//		if(flagScfFinishedForTotalMag&&isTotal) {flagScfFinishedForTotalMag=false;tmpMag.add(new ArrayList<Double>());}
//		if(flagScfFinishedForAbsMag&&!isTotal) {flagScfFinishedForAbsMag=false;tmpMag.add(new ArrayList<Double>());}
//	}
	public void addMag(double mag, int ind) {
		//int == 0: absoluteMag
		//int == 1: totalMag
		//int == 2: totalMagy
		//int == 3: totalMagz
		ArrayList<ArrayList<Double>> tmpMag = (ind==0 ? absoluteMag : (ind==1 ? totalMag : (ind==2 ? totalMagy : (ind==3 ? totalMagz : null))));
		if(tmpMag==null) {return;}
		if(tmpMag.isEmpty()) {tmpMag.add(new ArrayList<Double>());}
		tmpMag.get(tmpMag.size()-1).add(mag);
		
		if(flagScfFinishedForAbsMag && ind==0) {flagScfFinishedForAbsMag=false;tmpMag.add(new ArrayList<Double>());}
		if(flagScfFinishedForTotalMag && ind==1) {flagScfFinishedForTotalMag=false;tmpMag.add(new ArrayList<Double>());}
		if(flagScfFinishedForTotalMagy && ind==2) {flagScfFinishedForTotalMagy=false;tmpMag.add(new ArrayList<Double>());}
		if(flagScfFinishedForTotalMagz && ind==3) {flagScfFinishedForTotalMagz=false;tmpMag.add(new ArrayList<Double>());}
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
		if(line.contains("Frequency")) {//phonon DOS
			try {
				String[] parts1 = line.trim().split("\\s+");//split the string by whitespaces
				fermiDos=null;
				dosHeader.clear();
				for(int i=0;i<parts1.length;i++) {
					dosHeader.add(parts1[i]);
				}
			}
			catch(Exception e) {
				e.printStackTrace();
			}
		}
		else {//electronic DOS, from dos.x
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
		else if(EnumFileCategory.phononBandsGnu.equals(fileCategory)) {
			if(!phononBandsDatArray.isEmpty()) {
				strTmp+="Phonon: "+phononBandsDatArray.get(0).size()+" bands, "+
						phononBandsDatArray.size()+" q-points detected.\n";
				if(!this.phononKPoints.isEmpty()) {
					strTmp+="High symmetry q-points read from matdyn input file:\n";
				}
				for(Kpoint kp : this.phononKPoints) {
					if(kp!=null) {
						strTmp+="("+kp.getKx()+","+kp.getKy()+","+kp.getKz()+"),"+kp.getNk()+" points, "+kp.getLabel()+"\n";
					}
				}
			}
			else {
				strTmp+="Phonon bands: no data read.\n";
			}
		}
		else if(EnumFileCategory.stdout.equals(fileCategory)) {
			//stdout file
			strTmp+="Standard output file.\n";
			//calculation type
			strTmp+="Detected calculation type:";
			if(nstep==1 && hasScf) {strTmp+="SCF,";}
			if(isPW) {strTmp+="pw program:";}
			if(isMD) {strTmp+="MD,";}
			if(isOpt) {strTmp+="Optimization,";}
			if(isNscf) {strTmp+="NSCF,";}
			if(isDos) {strTmp+="DOS,";}
			if(isPH) {strTmp+="Phonon,";}
			if(isNeb) {strTmp+="NEB,";}
			if(isHybrid) {strTmp+="Hybrid functional,";}
			
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
			
			strTmp += "\n";
			
			//total energy
			//int cnt = 0;
			if(isMD || isOpt || hasScf) {
				strTmp += printArray(energyArray, "Total energy (Ry):", "Total energy converged (Ry):");
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
			
			//NEB
			if(isNeb) {
				if(!this.nebBarrierFwd.isEmpty() || !this.nebBarrierBwd.isEmpty()) {
					strTmp+="Activation energy forward:";
					for(Double val:nebBarrierFwd) {
						if(val!=null) {strTmp+=(val.toString()+",");}
					}
					strTmp+=" eV\n";
					
					strTmp+="Activation energy backward:";
					for(Double val:nebBarrierBwd) {
						if(val!=null) {strTmp+=(val.toString()+",");}
					}
					strTmp+=" eV\n";
				}
				if(!nebEnergy.isEmpty() || !nebError.isEmpty()) {
					//+nebEnergy.size()+","+nebEnergy.get(0).size()
					strTmp += "Total energy of each image(eV):";
					strTmp += this.printArray(nebEnergy, "", "","image");
					
					strTmp += "Error of each image(eV/A):";
					strTmp += this.printArray(nebError, "", "","image");
				}
			}
			
			//magnetization
			//int cnt_mag = 0;
			if(isMD || isOpt || hasScf) {
				if(!totalMag.isEmpty() || !absoluteMag.isEmpty()) {
					if(!totalMagy.isEmpty() || !totalMagz.isEmpty()) {
						strTmp+="Non collinear magnetism detected.\nTotal magnetization in x (Bohr mag/cell):";
					}
					else {
						strTmp+="Collinear magnetism calculation.\nTotal magnetization (Bohr mag/cell):";
					}
					
					strTmp += printArray(totalMag, "", "");
					
					if(!totalMagy.isEmpty() || !totalMagz.isEmpty()) {
						strTmp +="Total magnetization in y(Bohr mag/cell):";
						strTmp += printArray(totalMagy, "", "");
						
						strTmp +="Total magnetization in z(Bohr mag/cell):";
						strTmp += printArray(totalMagy, "", "");
					}
					
					strTmp+="Absolute magnetization (Bohr mag/cell):";
					strTmp += printArray(absoluteMag, "", "");
					
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
			
			strTmp += "\n";
			
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
			
			if(this.isPH) {
				int i=0;
				if(!this.phOutInfo.isEmpty()) {
					strTmp+="Phonon frequencies on the following q points:\n";
				}
				for(String st : phOutInfo) {
					i++;
					strTmp+=("----"+i+"th q-point:\n"+st+"\n");	
				}
				
				strTmp+="\n";
				if(!phononDielectricInfo.isEmpty()) {
					strTmp+="Dielectric tensor calculation detected. ";
					if(phononDielectricInfo.contains("Effective charges")) {
						strTmp+="Effective charge calculation detected.";
					}
					strTmp+=("\n"+phononDielectricInfo);
					
				}
				
			}
		
		}
		strTmp+="\n";
		return strTmp;
	}
	private String printArray(ArrayList<ArrayList<Double>> arrTmp, String smallTitle, String largeTitle) {
		return printArray(arrTmp, smallTitle, largeTitle,"Step ");
	}
	private String printArray(ArrayList<ArrayList<Double>> arrTmp, String smallTitle, String largeTitle, String seperatStr) {
		String strTmp = "";
		int cnt = 0;
		if(arrTmp.size()<=2) {
			strTmp+=smallTitle;
			for(ArrayList<Double> ard:arrTmp) {
				if(ard!=null) {
					cnt++;
					if(ard.isEmpty()) {continue;}
					strTmp+=(seperatStr+Integer.toString(cnt)+": ");
					for(Double val:ard) {
						if(val!=null) {strTmp+=(val.toString()+",");
							//ShowAlert.showAlert("Debug", val.toString());
						}
					}
					strTmp+="\n";
				}
			}
		}
		else {
			strTmp+=largeTitle;
			for(ArrayList<Double> ard:arrTmp) {
				if(ard!=null) {
					cnt++;
					if(ard.isEmpty()) {continue;}
					strTmp+=(seperatStr+Integer.toString(cnt)+": "+ard.get(ard.size()-1).toString()+",");
				}
				if((cnt % 5) == 0) {
					strTmp+="\n";
				}
			}
			strTmp+="\n";
		}
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
	public ArrayList<ArrayList<Double>> getTotalMag(){
		return this.totalMag;
	}
	public ArrayList<ArrayList<Double>> getTotalMagy(){
		return this.totalMagy;
	}
	public ArrayList<ArrayList<Double>> getTotalMagz(){
		return this.totalMagz;
	}
	public ArrayList<ArrayList<Double>> getAbsoluteMag(){
		return this.absoluteMag;
	}
	public ArrayList<Kpoint> getPhononK() {
		return this.phononKPoints;
	}
	public ArrayList<ArrayList<Double>> getPhononDat(){
		return this.phononBandsDatArray;
	}
	public ArrayList<ArrayList<Double>> getNebEnergy(){
		return this.nebEnergy;
	}
	public ArrayList<ArrayList<Double>> getNebError(){
		return this.nebError;
	}
	public ArrayList<Double> getNebBarrierBwd(){
		return this.nebBarrierBwd;
	}
	public ArrayList<Double> getNebBarrierFwd(){
		return this.nebBarrierFwd;
	}
	
}
